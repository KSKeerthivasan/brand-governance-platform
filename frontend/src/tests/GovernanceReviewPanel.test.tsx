import { describe, it, expect } from 'vitest';
import React from 'react';
import { renderToString } from 'react-dom/server';
import {
  GovernanceReviewPanel,
  getHumanReadableTitle,
  getWhyItMatters,
  getWhatToDo
} from '../components/GovernanceReviewPanel';
import { GovernanceFinding, GovernanceRun, CorrectionSuggestion } from '../types';

describe('GovernanceReviewPanel - UX Redesign & Usability', () => {
  const mockFindingCrit: GovernanceFinding = {
    id: 'f-1',
    governance_run_id: 'run-1',
    category: 'unsupported_claim',
    severity: 'critical',
    title: 'Unsupported Claim in Poster Image: "100% Virus Removal in 30 Seconds"',
    explanation: 'The creative contains a performance claim without supporting clinical trial documentation in the active Knowledge Base.',
    source_citation: 'SUPPORTING EVIDENCE NOT FOUND',
    text_excerpt: '100% Virus Removal in 30 Seconds',
    recommended_action: 'Remove or substantiate claim with approved clinical evidence.',
    status: 'verified_issue',
    created_at: '2026-11-03T12:00:00Z'
  };

  const mockFindingContrast1: GovernanceFinding = {
    id: 'f-contrast-1',
    governance_run_id: 'run-1',
    category: 'contrast',
    severity: 'warning',
    title: 'Insufficient Text Contrast (1.8:1)',
    explanation: 'Headline text "V Protect" has a contrast ratio of 1.8:1 against the light background, which fails WCAG AA 4.5:1 standards.',
    source_citation: 'WCAG 2.1 AA Standards',
    text_excerpt: "'V Protect' Contrast: 1.8:1",
    recommended_action: 'Increase text contrast against background in design tool.',
    status: 'verified_issue',
    created_at: '2026-11-03T12:00:00Z'
  };

  const mockFindingContrast2: GovernanceFinding = {
    id: 'f-contrast-2',
    governance_run_id: 'run-1',
    category: 'contrast',
    severity: 'warning',
    title: 'Insufficient Text Contrast (2.3:1)',
    explanation: 'Subheading text "Premium Protection" has a contrast ratio of 2.3:1 against the background.',
    source_citation: 'WCAG 2.1 AA Standards',
    text_excerpt: "'Premium Protection' Contrast: 2.3:1",
    recommended_action: 'Increase text contrast against background in design tool.',
    status: 'verified_issue',
    created_at: '2026-11-03T12:00:00Z'
  };

  const mockFindingPass: GovernanceFinding = {
    id: 'f-pass',
    governance_run_id: 'run-1',
    category: 'dimensions',
    severity: 'info',
    title: 'Aspect Ratio Within Permitted Range (0.77:1 vs 1:1)',
    explanation: 'Creative aspect ratio 0.77:1 is within the permitted range of 0.75:1 to 1.25:1 for Social Media (standard 1:1 ±25%).',
    source_citation: 'Channel Standards (Social Media)',
    text_excerpt: '0.77:1 (Permitted: 0.75:1–1.25:1)',
    recommended_action: 'No change needed.',
    status: 'passed_check',
    created_at: '2026-11-03T12:00:00Z'
  };

  const mockFindingOcrUncertain: GovernanceFinding = {
    id: 'f-ocr',
    governance_run_id: 'run-1',
    category: 'unsupported_claim',
    severity: 'warning',
    title: 'Low OCR Confidence: Manual Verification Required',
    explanation: 'OCR detected ambiguous wording in lower banner area. Manual review required.',
    source_citation: 'OCR Engine Detection',
    text_excerpt: 'ambiguous text snippet',
    recommended_action: 'Manually verify poster text.',
    status: 'unable_to_verify',
    created_at: '2026-11-03T12:00:00Z'
  };

  const mockFindingLogoMissing: GovernanceFinding = {
    id: 'f-logo',
    governance_run_id: 'run-1',
    category: 'logo',
    severity: 'info',
    title: 'Logo Verification Inconclusive: Reference Asset Missing',
    explanation: 'No approved brand logo file exists in the active Knowledge Base for automated visual matching.',
    source_citation: 'Brand Asset Catalog',
    recommended_action: 'Upload approved brand logo to Knowledge Library.',
    status: 'unable_to_verify',
    created_at: '2026-11-03T12:00:00Z'
  };

  const mockFindingTypoHeuristic: GovernanceFinding = {
    id: 'f-typo',
    governance_run_id: 'run-1',
    category: 'layout',
    severity: 'info',
    title: 'Typography Hierarchy Heuristic Signal: Positive',
    explanation: 'Estimated visual hierarchy exhibits clear size distinction between headline and body text.',
    source_citation: 'Layout Heuristics Engine',
    recommended_action: 'No change needed.',
    status: 'passed_check',
    created_at: '2026-11-03T12:00:00Z'
  };

  describe('Human-Readable Title Mapping', () => {
    it('converts technical claim titles into plain business titles', () => {
      const title = getHumanReadableTitle(mockFindingCrit);
      expect(title).toBe('Unapproved product claim detected in poster');
    });

    it('converts contrast error titles into plain readability titles', () => {
      const title = getHumanReadableTitle(mockFindingContrast1);
      expect(title).toBe('Some poster text is difficult to read');
    });

    it('converts aspect ratio passes into clear permitted range titles', () => {
      const title = getHumanReadableTitle(mockFindingPass);
      expect(title).toBe('Aspect ratio within permitted standard');
    });

    it('converts low OCR confidence into verification requests without raw percentages', () => {
      const title = getHumanReadableTitle(mockFindingOcrUncertain);
      expect(title).toBe('Text detection needs manual verification');
    });

    it('converts missing logo reference into clear actionable title', () => {
      const title = getHumanReadableTitle(mockFindingLogoMissing);
      expect(title).toBe('Official brand logo could not be verified');
    });

    it('converts typography hierarchy heuristic titles into plain phrasing', () => {
      const title = getHumanReadableTitle(mockFindingTypoHeuristic);
      expect(title).toBe('Text hierarchy looks appropriate');
    });
  });

  describe('3 Core Questions Answered (What, Why, Action)', () => {
    it('provides clear "Why it matters" for unapproved product claims', () => {
      const why = getWhyItMatters(mockFindingCrit);
      expect(why).toContain('mislead customers');
      expect(why).toContain('regulatory complaints');
    });

    it('provides clear "Why it matters" for contrast failures', () => {
      const why = getWhyItMatters(mockFindingContrast1);
      expect(why).toContain('Low-contrast text');
      expect(why).toContain('accessibility standards');
    });

    it('provides clear "Why it matters" for missing logo library assets', () => {
      const why = getWhyItMatters(mockFindingLogoMissing);
      expect(why).toContain('Knowledge Library');
    });

    it('provides artwork tool notice in "What to do" when modifying poster artwork', () => {
      const action = getWhatToDo(mockFindingContrast1);
      expect(action).toContain('design tool');
      expect(action).toContain('Your poster cannot be modified directly inside Inkloom AI');
    });

    it('provides "No change required" for passed checks', () => {
      const action = getWhatToDo(mockFindingPass);
      expect(action).toBe('No change required. This check passed.');
    });
  });

  describe('Panel Rendering & Review Experience', () => {
    const defaultRun: GovernanceRun = {
      id: 'run-1',
      content_version_id: 'ver-1',
      overall_status: 'failed',
      rules_evaluated_count: 10,
      facts_evaluated_count: 8,
      findings_count: 6,
      created_at: '2026-11-03T12:00:00Z',
      findings: [
        mockFindingCrit,
        mockFindingContrast1,
        mockFindingContrast2,
        mockFindingPass,
        mockFindingOcrUncertain,
        mockFindingLogoMissing
      ]
    };

    it('renders Advertisement Review header with dynamic outcome badge and authoritative status', () => {
      const html = renderToString(
        React.createElement(GovernanceReviewPanel, {
          latestGovRun: defaultRun,
          checkedVersionNum: 2,
          checkedVersionId: 'ver-12345678',
          isDirty: false,
          isPdf: false,
          pdfPageCount: 0,
          selectedPage: 1,
          onSelectPage: () => {},
          govError: null,
          checking: false,
          onRunChecks: () => {},
          suggestions: {},
          suggestionApplying: false,
          onAcceptSuggestion: async () => {},
          onRejectSuggestion: async () => {},
          onOpenCustomEdit: () => {},
          suggestionBanner: null,
          onCloseSuggestionBanner: () => {}
        })
      );

      expect(html).toContain('Advertisement Review');
      expect(html).toContain('Changes Required');
      expect(html).toContain('Authoritative:');
      expect(html).toContain('FAILED');
      expect(html).toContain('Version');
      expect(html).toContain('2');
    });

    it('displays 3 dynamic counters: Needs Fixes, Needs Review, Passed', () => {
      const html = renderToString(
        React.createElement(GovernanceReviewPanel, {
          latestGovRun: defaultRun,
          checkedVersionNum: 2,
          checkedVersionId: 'ver-12345678',
          isDirty: false,
          isPdf: false,
          pdfPageCount: 0,
          selectedPage: 1,
          onSelectPage: () => {},
          govError: null,
          checking: false,
          onRunChecks: () => {},
          suggestions: {},
          suggestionApplying: false,
          onAcceptSuggestion: async () => {},
          onRejectSuggestion: async () => {},
          onOpenCustomEdit: () => {},
          suggestionBanner: null,
          onCloseSuggestionBanner: () => {}
        })
      );

      expect(html).toContain('Needs Fixes');
      expect(html).toContain('Needs Review');
      expect(html).toContain('Passed');
      // Needs Fixes: mockFindingCrit, mockFindingContrast1, mockFindingContrast2 = 3
      // Needs Review: mockFindingOcrUncertain, mockFindingLogoMissing = 2
      // Passed: mockFindingPass = 1
      expect(html).toContain('>3</div>'); // Needs Fixes count
      expect(html).toContain('>2</div>'); // Needs Review count
      expect(html).toContain('>1</div>'); // Passed count
    });

    it('groups repetitive contrast findings into a single consolidated card', () => {
      const html = renderToString(
        React.createElement(GovernanceReviewPanel, {
          latestGovRun: defaultRun,
          checkedVersionNum: 2,
          checkedVersionId: 'ver-12345678',
          isDirty: false,
          isPdf: false,
          pdfPageCount: 0,
          selectedPage: 1,
          onSelectPage: () => {},
          govError: null,
          checking: false,
          onRunChecks: () => {},
          suggestions: {},
          suggestionApplying: false,
          onAcceptSuggestion: async () => {},
          onRejectSuggestion: async () => {},
          onOpenCustomEdit: () => {},
          suggestionBanner: null,
          onCloseSuggestionBanner: () => {}
        })
      );

      // Consolidated contrast card
      expect(html).toContain('Text readability issues — 2 regions affected');
      expect(html).toContain('Affected Regions:');
      expect(html).toContain('V Protect');
      expect(html).toContain('Premium Protection');
      expect(html).toContain('1.8:1');
      expect(html).toContain('2.3:1');
    });

    it('structures findings with What we found, Why it matters, What to do', () => {
      const html = renderToString(
        React.createElement(GovernanceReviewPanel, {
          latestGovRun: defaultRun,
          checkedVersionNum: 2,
          checkedVersionId: 'ver-12345678',
          isDirty: false,
          isPdf: false,
          pdfPageCount: 0,
          selectedPage: 1,
          onSelectPage: () => {},
          govError: null,
          checking: false,
          onRunChecks: () => {},
          suggestions: {},
          suggestionApplying: false,
          onAcceptSuggestion: async () => {},
          onRejectSuggestion: async () => {},
          onOpenCustomEdit: () => {},
          suggestionBanner: null,
          onCloseSuggestionBanner: () => {}
        })
      );

      expect(html).toContain('What we found');
      expect(html).toContain('Why it matters');
      expect(html).toContain('What to do');
    });

    it('prompts user verification for unconfirmed OCR detections without fake percentages', () => {
      const html = renderToString(
        React.createElement(GovernanceReviewPanel, {
          latestGovRun: {
            id: 'run-ocr',
            content_version_id: 'ver-1',
            overall_status: 'warnings',
            rules_evaluated_count: 5,
            facts_evaluated_count: 4,
            findings_count: 1,
            created_at: '2026-11-03T12:00:00Z',
            findings: [mockFindingOcrUncertain]
          },
          checkedVersionNum: 1,
          checkedVersionId: 'ver-1',
          isDirty: false,
          isPdf: false,
          pdfPageCount: 0,
          selectedPage: 1,
          onSelectPage: () => {},
          govError: null,
          checking: false,
          onRunChecks: () => {},
          suggestions: {},
          suggestionApplying: false,
          onAcceptSuggestion: async () => {},
          onRejectSuggestion: async () => {},
          onOpenCustomEdit: () => {},
          suggestionBanner: null,
          onCloseSuggestionBanner: () => {}
        })
      );

      expect(html).toContain('Text detection needs verification:');
      expect(html).toContain('captured by local OCR and may contain recognition inaccuracies');
      // No raw fake percent invented when undefined
      expect(html).not.toContain('OCR Confidence: NaN%');
      expect(html).not.toContain('OCR Confidence: undefined%');
    });

    it('renders suggested correction with diff and explicit artwork notice for poster targets', () => {
      const suggestion: CorrectionSuggestion = {
        id: 'sug-1',
        finding_id: 'f-1',
        content_item_id: 'item-1',
        content_version_id: 'ver-1',
        source_checksum: 'chk-1',
        confidence: 'high',
        target_type: 'poster_image',
        original_text: '100% Virus Removal in 30 Seconds',
        proposed_text: 'Helps protect surfaces from common viruses',
        explanation: 'Replace unverified 100% viral elimination claim with qualified supportive wording.',
        correction_type: 'qualify_claim',
        evidence_source: 'V Protect Product Factsheet (Section 3)',
        can_auto_apply: false,
        status: 'pending',
        created_at: '2026-11-03T12:00:00Z'
      };

      const html = renderToString(
        React.createElement(GovernanceReviewPanel, {
          latestGovRun: defaultRun,
          checkedVersionNum: 2,
          checkedVersionId: 'ver-1',
          isDirty: false,
          isPdf: false,
          pdfPageCount: 0,
          selectedPage: 1,
          onSelectPage: () => {},
          govError: null,
          checking: false,
          onRunChecks: () => {},
          suggestions: { 'f-1': suggestion },
          suggestionApplying: false,
          onAcceptSuggestion: async () => {},
          onRejectSuggestion: async () => {},
          onOpenCustomEdit: () => {},
          suggestionBanner: null,
          onCloseSuggestionBanner: () => {}
        })
      );

      expect(html).toContain('Suggested correction');
      expect(html).toContain('Proposed:');
      expect(html).toContain('Helps protect surfaces from common viruses');
      expect(html).toContain('Your poster cannot be modified directly inside Inkloom AI. Update it in your design tool and upload the revised version.');
      expect(html).toContain('Acknowledge Guidance');
      expect(html).toContain('Reject');
    });

    it('renders Multi-Page PDF banner and page filter buttons when isPdf is true', () => {
      const pdfFindings: GovernanceFinding[] = [
        { ...mockFindingCrit, page_number: 1 },
        { ...mockFindingPass, page_number: 2 }
      ];

      const html = renderToString(
        React.createElement(GovernanceReviewPanel, {
          latestGovRun: {
            id: 'run-pdf',
            content_version_id: 'ver-pdf',
            overall_status: 'failed',
            rules_evaluated_count: 6,
            facts_evaluated_count: 5,
            findings_count: 2,
            created_at: '2026-11-03T12:00:00Z',
            findings: pdfFindings
          },
          checkedVersionNum: 1,
          checkedVersionId: 'ver-pdf',
          isDirty: false,
          isPdf: true,
          pdfPageCount: 2,
          selectedPage: 1,
          onSelectPage: () => {},
          govError: null,
          checking: false,
          onRunChecks: () => {},
          suggestions: {},
          suggestionApplying: false,
          onAcceptSuggestion: async () => {},
          onRejectSuggestion: async () => {},
          onOpenCustomEdit: () => {},
          suggestionBanner: null,
          onCloseSuggestionBanner: () => {}
        })
      );

      expect(html).toContain('All 2 Pages Analysed (1 With Findings)');
      expect(html).toMatch(/Pg.*1/);
      expect(html).toMatch(/Pg.*2/);
      expect(html).toContain('Caption');
    });
  });
});
