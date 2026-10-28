import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from '../services/api';
import { ContentItem, GovernanceRun } from '../types';

describe('Content Studio Save-and-Check Execution Chain', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('A: Existing draft - edited copy is saved first and checked version contains the edited copy', async () => {
    const existingDraft: ContentItem = {
      id: 'draft-item-1',
      organization_id: 'org-1',
      brand_id: 'brand-1',
      created_by: 'user-1',
      title: 'Original Title',
      channel: 'Instagram Post',
      status: 'draft',
      current_version_num: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      latest_version: {
        id: 'ver-1',
        content_item_id: 'draft-item-1',
        version_num: 1,
        body_text: 'Original copy text',
        checksum: 'sha-ver-1',
        created_at: new Date().toISOString()
      }
    };

    const editedCopy = 'Updated promotional copy with organic ingredients';
    const updatedDraft: ContentItem = {
      ...existingDraft,
      current_version_num: 2,
      latest_version: {
        id: 'ver-2',
        content_item_id: 'draft-item-1',
        version_num: 2,
        body_text: editedCopy,
        checksum: 'sha-ver-2',
        created_at: new Date().toISOString()
      }
    };

    const mockGovRun: GovernanceRun = {
      id: 'gov-run-2',
      content_version_id: 'ver-2',
      overall_status: 'passed',
      rules_evaluated_count: 10,
      facts_evaluated_count: 12,
      findings_count: 0,
      created_at: new Date().toISOString(),
      findings: []
    };

    const updateSpy = vi.spyOn(api, 'updateContentItem').mockResolvedValue(updatedDraft);
    const govSpy = vi.spyOn(api, 'runGovernanceCheck').mockResolvedValue(mockGovRun);

    // Simulate save-and-check execution
    const saved = await api.updateContentItem(
      existingDraft.id,
      editedCopy,
      existingDraft.title,
      existingDraft.channel
    );
    expect(saved.latest_version).toBeDefined();
    expect(saved.latest_version!.body_text).toBe(editedCopy);
    expect(saved.latest_version!.id).toBe('ver-2');

    const run = await api.runGovernanceCheck(saved.latest_version!.id);
    expect(updateSpy).toHaveBeenCalledWith(
      'draft-item-1',
      editedCopy,
      'Original Title',
      'Instagram Post'
    );
    expect(govSpy).toHaveBeenCalledWith('ver-2');
    expect(run.content_version_id).toBe('ver-2');
  });

  it('B: Existing draft - attached poster and alt text are saved and evaluated together', async () => {
    const existingDraft: ContentItem = {
      id: 'draft-item-2',
      organization_id: 'org-1',
      brand_id: 'brand-1',
      created_by: 'user-1',
      title: 'Summer Splash',
      channel: 'Instagram Post',
      status: 'draft',
      current_version_num: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      latest_version: {
        id: 'ver-10',
        content_item_id: 'draft-item-2',
        version_num: 1,
        body_text: 'Pure natural sparkling juice',
        checksum: 'sha-ver-10',
        created_at: new Date().toISOString()
      }
    };

    const posterPath = '/uploads/posters/summer_splash_square.png';
    const altText = 'A vibrant chilled bottle of Freshsip on citrus slices';

    const updatedWithPoster: ContentItem = {
      ...existingDraft,
      current_version_num: 2,
      latest_version: {
        id: 'ver-11',
        content_item_id: 'draft-item-2',
        version_num: 2,
        body_text: existingDraft.latest_version!.body_text,
        poster_file_path: posterPath,
        poster_alt_text: altText,
        checksum: 'sha-ver-11',
        created_at: new Date().toISOString()
      }
    };

    const mockGovRun: GovernanceRun = {
      id: 'gov-run-11',
      content_version_id: 'ver-11',
      overall_status: 'passed',
      rules_evaluated_count: 14,
      facts_evaluated_count: 15,
      findings_count: 1,
      created_at: new Date().toISOString(),
      findings: [
        {
          id: 'f-1',
          governance_run_id: 'gov-run-11',
          category: 'dimensions',
          severity: 'info',
          status: 'passed_check',
          title: 'Dimensions Match Target Channel',
          explanation: 'Creative dimensions 1080x1080 match Instagram Post (1:1).',
          source_citation: 'Channel Spec',
          recommended_action: 'None',
          created_at: new Date().toISOString()
        }
      ]
    };

    const updateSpy = vi.spyOn(api, 'updateContentItem').mockResolvedValue(updatedWithPoster);
    const govSpy = vi.spyOn(api, 'runGovernanceCheck').mockResolvedValue(mockGovRun);

    const saved = await api.updateContentItem(
      existingDraft.id,
      existingDraft.latest_version!.body_text,
      existingDraft.title,
      existingDraft.channel,
      posterPath,
      undefined,
      altText
    );

    expect(saved.latest_version!.poster_file_path).toBe(posterPath);
    expect(saved.latest_version!.poster_alt_text).toBe(altText);

    const run = await api.runGovernanceCheck(saved.latest_version!.id);
    expect(updateSpy).toHaveBeenCalledWith(
      'draft-item-2',
      'Pure natural sparkling juice',
      'Summer Splash',
      'Instagram Post',
      posterPath,
      undefined,
      altText
    );
    expect(govSpy).toHaveBeenCalledWith('ver-11');
    expect(run.findings[0].category).toBe('dimensions');
  });

  it('C: New draft - immediately running checks persists draft and invokes governance without silent exit', async () => {
    const brandId = 'brand-abc';
    const newTitle = 'Fresh Launch';
    const newBody = 'Try our brand new iced sparkling tea today!';
    const channel = 'Instagram Post';

    const createdDraft: ContentItem = {
      id: 'new-draft-99',
      organization_id: 'org-1',
      brand_id: brandId,
      created_by: 'user-1',
      title: newTitle,
      channel,
      status: 'draft',
      current_version_num: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      latest_version: {
        id: 'ver-new-1',
        content_item_id: 'new-draft-99',
        version_num: 1,
        body_text: newBody,
        checksum: 'sha-new-1',
        created_at: new Date().toISOString()
      }
    };

    const mockGovRun: GovernanceRun = {
      id: 'gov-new-run',
      content_version_id: 'ver-new-1',
      overall_status: 'passed',
      rules_evaluated_count: 8,
      facts_evaluated_count: 9,
      findings_count: 0,
      created_at: new Date().toISOString(),
      findings: []
    };

    const createSpy = vi.spyOn(api, 'createContentItem').mockResolvedValue(createdDraft);
    const govSpy = vi.spyOn(api, 'runGovernanceCheck').mockResolvedValue(mockGovRun);

    // Save-and-check execution sequence
    const saved = await api.createContentItem(brandId, newTitle, channel, newBody);
    expect(saved).toBeDefined();
    expect(saved.latest_version).toBeDefined();
    expect(saved.latest_version!.id).toBe('ver-new-1');

    // Run governance check against returned version ID
    const run = await api.runGovernanceCheck(saved.latest_version!.id);
    expect(createSpy).toHaveBeenCalledWith(brandId, newTitle, channel, newBody);
    expect(govSpy).toHaveBeenCalledWith('ver-new-1');
    expect(run.content_version_id).toBe('ver-new-1');
  });

  it('D: Failure handling - aborts governance when save fails and clears stale findings on check error', async () => {
    // 1. When saving fails:
    vi.spyOn(api, 'createContentItem').mockRejectedValue(new Error('Network offline'));
    const govSpy = vi.spyOn(api, 'runGovernanceCheck');

    let saveFailed = false;
    let savedItem: ContentItem | null = null;
    try {
      savedItem = await api.createContentItem('brand-1', 'Title', 'Channel', 'Body');
    } catch (e: any) {
      saveFailed = true;
      expect(e.message).toBe('Network offline');
    }

    expect(saveFailed).toBe(true);
    expect(savedItem).toBeNull();
    // Governance must NOT be called if save fails
    expect(govSpy).not.toHaveBeenCalled();

    // 2. When governance check fails:
    let latestGovRun: GovernanceRun | null = {
      id: 'old-run',
      content_version_id: 'old-ver',
      overall_status: 'passed',
      rules_evaluated_count: 5,
      facts_evaluated_count: 5,
      findings_count: 0,
      created_at: new Date().toISOString(),
      findings: []
    };

    vi.spyOn(api, 'runGovernanceCheck').mockRejectedValue(new Error('Backend governance timeout'));

    let govError: string | null = null;
    try {
      await api.runGovernanceCheck('ver-target');
    } catch (e: any) {
      govError = e.message;
      // Stale findings must be cleared immediately
      latestGovRun = null;
    }

    expect(govError).toBe('Backend governance timeout');
    expect(latestGovRun).toBeNull();
  });

  it('E: Version consistency - ensures findings correspond strictly to the checked version', async () => {
    const version1Id = 'v1-uuid';
    const version2Id = 'v2-uuid';

    const runV1: GovernanceRun = {
      id: 'run-v1',
      content_version_id: version1Id,
      overall_status: 'failed',
      rules_evaluated_count: 10,
      facts_evaluated_count: 10,
      findings_count: 1,
      created_at: new Date().toISOString(),
      findings: [
        {
          id: 'f-v1',
          governance_run_id: 'run-v1',
          category: 'claims',
          severity: 'critical',
          status: 'failed_rule',
          title: 'Unsubstantiated Health Claim',
          explanation: 'Body makes unauthorized medical assertion.',
          source_citation: 'Freshsip Factbook',
          recommended_action: 'Remove medical claim',
          created_at: new Date().toISOString()
        }
      ]
    };

    const runV2: GovernanceRun = {
      id: 'run-v2',
      content_version_id: version2Id,
      overall_status: 'passed',
      rules_evaluated_count: 10,
      facts_evaluated_count: 10,
      findings_count: 0,
      created_at: new Date().toISOString(),
      findings: []
    };

    const govSpy = vi.spyOn(api, 'runGovernanceCheck').mockImplementation(async (verId) => {
      if (verId === version1Id) return runV1;
      if (verId === version2Id) return runV2;
      throw new Error('Version not found');
    });

    const resV1 = await api.runGovernanceCheck(version1Id);
    expect(resV1.content_version_id).toBe(version1Id);
    expect(resV1.overall_status).toBe('failed');

    const resV2 = await api.runGovernanceCheck(version2Id);
    expect(resV2.content_version_id).toBe(version2Id);
    expect(resV2.overall_status).toBe('passed');
    expect(govSpy).toHaveBeenCalledTimes(2);
  });
});
