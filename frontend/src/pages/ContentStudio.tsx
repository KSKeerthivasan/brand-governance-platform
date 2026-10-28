import React, { useState, useEffect, useRef } from 'react';
import {
  FileEdit,
  Play,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Send,
  History,
  ShieldAlert,
  Hash,
  Sparkles,
  Info,
  Clock,
  Plus,
  Image as ImageIcon,
  Upload,
  Trash2,
  Layers,
  HelpCircle
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { StatusBadge } from '../components/StatusBadge';
import { ContentItem, ContentVersion, GovernanceRun, Brand, BrandAsset, CorrectionSuggestion } from '../types';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

export const ContentStudio: React.FC = () => {
  const { role } = useAuth();
  const [contentList, setContentList] = useState<ContentItem[]>([]);
  const [selectedContent, setSelectedContent] = useState<ContentItem | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [assets, setAssets] = useState<BrandAsset[]>([]);
  const [versions, setVersions] = useState<ContentVersion[]>([]);
  const [latestGovRun, setLatestGovRun] = useState<GovernanceRun | null>(null);

  // Form Editor State
  const [title, setTitle] = useState('');
  const [channel, setChannel] = useState('Social Media');
  const [bodyText, setBodyText] = useState('');
  const [selectedBrandId, setSelectedBrandId] = useState('');

  // Poster & Creative Asset State
  const [posterFilePath, setPosterFilePath] = useState<string | null>(null);
  const [posterAssetId, setPosterAssetId] = useState<string | null>(null);
  const [posterAltText, setPosterAltText] = useState('');
  const [posterPreviewUrl, setPosterPreviewUrl] = useState<string | null>(null);
  const [posterMeta, setPosterMeta] = useState<{
    width?: number;
    height?: number;
    color_mode?: string;
    format?: string;
    filename?: string;
  } | null>(null);
  const [uploadingPoster, setUploadingPoster] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Multi-Page PDF State
  const [isPdf, setIsPdf] = useState(false);
  const [pdfPageCount, setPdfPageCount] = useState(1);
  const [selectedPage, setSelectedPage] = useState(1);
  const [pdfPages, setPdfPages] = useState<Array<{
    page_number: number;
    width_pt: number;
    height_pt: number;
    width_px: number;
    height_px: number;
    orientation: string;
    aspect_ratio: string;
    image_url?: string;
  }>>([]);
  const [pageFilter, setPageFilter] = useState<'all' | number | 'caption'>('all');

  // Findings Drawer Filter
  const [findingsFilter, setFindingsFilter] = useState<'all' | 'text' | 'visual'>('all');

  // Status & Loading
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submitModalOpen, setSubmitModalOpen] = useState(false);
  const [submitNotes, setSubmitNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [checkedVersionId, setCheckedVersionId] = useState<string | null>(null);
  const [checkedVersionNum, setCheckedVersionNum] = useState<number | null>(null);
  const [govError, setGovError] = useState<string | null>(null);

  // Milestone 5D: Context-Preserving Correction Suggestions State
  const [suggestions, setSuggestions] = useState<Record<string, CorrectionSuggestion>>({});
  const [customEditModalOpen, setCustomEditModalOpen] = useState(false);
  const [activeSuggestionForEdit, setActiveSuggestionForEdit] = useState<CorrectionSuggestion | null>(null);
  const [customEditText, setCustomEditText] = useState('');
  const [suggestionApplying, setSuggestionApplying] = useState(false);
  const [suggestionBanner, setSuggestionBanner] = useState<{ type: 'success' | 'info' | 'error'; text: string } | null>(null);

  const isCreator = role === 'content_creator' || role === 'org_admin';

  const loadContents = async (silent = false) => {
    try {
      const [items, b, a] = await Promise.all([
        api.getContentItems(),
        api.getBrands(),
        api.getAssets()
      ]);
      setContentList(items);
      setBrands(b);
      setAssets(a);
      if (b.length > 0 && !selectedBrandId) {
        setSelectedBrandId(b[0].id);
      }
      if (!silent) {
        if (items.length > 0 && !selectedContent) {
          selectDraft(items[0]);
        }
      } else {
        if (selectedContent && !saving && !submitting && !checking) {
          const freshItem = items.find(i => i.id === selectedContent.id);
          if (freshItem) {
            setSelectedContent(freshItem);
            try {
              const vers = await api.getContentVersions(freshItem.id);
              setVersions(vers);
            } catch {
              // ignore
            }
          }
        }
      }
    } catch (err) {
      console.error('Failed to load content items:', err);
    }
  };

  useEffect(() => {
    loadContents(false);
  }, []);

  useAutoRefresh(() => {
    if (!saving && !submitting && !checking && !isDirty) {
      loadContents(true);
    }
  }, { intervalMs: 6000 });

  const selectDraft = async (item: ContentItem) => {
    setSelectedContent(item);
    setTitle(item.title);
    setChannel(item.channel);
    setSelectedBrandId(item.brand_id);
    setBodyText(item.latest_version?.body_text || '');
    setGovError(null);
    setIsDirty(false);

    // Restore poster details from version
    const ver = item.latest_version;
    if (ver && ver.poster_file_path) {
      setPosterFilePath(ver.poster_file_path);
      setPosterAssetId(ver.poster_asset_id || null);
      setPosterAltText(ver.poster_alt_text || '');
      const isPdfFile = Boolean(ver.is_pdf || ver.poster_file_path.toLowerCase().endsWith('.pdf'));
      setIsPdf(isPdfFile);
      setSelectedPage(1);
      setPageFilter('all');
      if (isPdfFile) {
        setPosterPreviewUrl(api.getPosterUrl(ver.id, 1));
        api.getPdfPages(ver.id).then(res => {
          setPdfPageCount(res.page_count || 1);
          setPdfPages(res.pages || []);
        }).catch(() => {
          setPdfPageCount(1);
          setPdfPages([]);
        });
      } else {
        setPosterPreviewUrl(api.getPosterUrl(ver.id));
        setPdfPageCount(1);
        setPdfPages([]);
      }
      setPosterMeta({
        filename: ver.poster_file_path.split(/[/\\]/).pop(),
        format: isPdfFile ? 'PDF' : 'Image'
      });
    } else {
      setPosterFilePath(null);
      setPosterAssetId(null);
      setPosterAltText('');
      setPosterPreviewUrl(null);
      setPosterMeta(null);
      setIsPdf(false);
      setPdfPageCount(1);
      setPdfPages([]);
      setSelectedPage(1);
      setPageFilter('all');
    }

    // Load versions
    try {
      const vers = await api.getContentVersions(item.id);
      setVersions(vers);

      // Load latest governance run for the current version
      if (item.latest_version) {
        try {
          const run = await api.getLatestGovernanceRun(item.latest_version.id);
          setLatestGovRun(run);
          setCheckedVersionId(item.latest_version.id);
          setCheckedVersionNum(item.latest_version.version_num);
          const sugMap: Record<string, CorrectionSuggestion> = {};
          if (run.findings) {
            run.findings.forEach(f => {
              if (f.suggestion) sugMap[f.id] = f.suggestion;
            });
          }
          setSuggestions(sugMap);
        } catch {
          setLatestGovRun(null);
          setCheckedVersionId(null);
          setCheckedVersionNum(null);
          setSuggestions({});
        }
      } else {
        setLatestGovRun(null);
        setCheckedVersionId(null);
        setCheckedVersionNum(null);
        setSuggestions({});
      }
    } catch (err) {
      console.error('Failed to load draft version history:', err);
    }
  };

  const handleCreateNewDraft = () => {
    setSelectedContent(null);
    setTitle('New Campaign Draft');
    setChannel('Social Media');
    setBodyText('');
    setSuggestions({});
    setSuggestionBanner(null);
    setPosterFilePath(null);
    setPosterAssetId(null);
    setPosterAltText('');
    setPosterPreviewUrl(null);
    setPosterMeta(null);
    setIsPdf(false);
    setPdfPageCount(1);
    setPdfPages([]);
    setSelectedPage(1);
    setPageFilter('all');
    setLatestGovRun(null);
    setCheckedVersionId(null);
    setCheckedVersionNum(null);
    setGovError(null);
    setIsDirty(false);
    setVersions([]);
    if (brands.length > 0) {
      setSelectedBrandId(brands[0].id);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingPoster(true);
    try {
      const uploadRes = await api.uploadPoster(file);
      const isPdfFile = uploadRes.format === 'PDF' || file.name.toLowerCase().endsWith('.pdf');
      setPosterFilePath(uploadRes.file_path);
      setPosterAssetId(null);
      setIsPdf(isPdfFile);
      setPdfPageCount(uploadRes.page_count || 1);
      setPdfPages(uploadRes.pages || []);
      setSelectedPage(1);
      setPageFilter('all');
      setPosterMeta({
        filename: uploadRes.filename,
        width: uploadRes.width,
        height: uploadRes.height,
        color_mode: uploadRes.color_mode,
        format: uploadRes.format
      });
      if (isPdfFile) {
        setPosterPreviewUrl(null);
      } else {
        setPosterPreviewUrl(URL.createObjectURL(file));
      }
      setIsDirty(true);
    } catch (err: any) {
      alert(`Creative upload failed: ${err.message}`);
    } finally {
      setUploadingPoster(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handlePageSelect = (pageNum: number) => {
    setSelectedPage(pageNum);
    if (checkedVersionId && isPdf) {
      setPosterPreviewUrl(api.getPosterUrl(checkedVersionId, pageNum));
    }
  };

  const handleSelectBrandAsset = (assetId: string) => {
    const asset = assets.find(a => a.id === assetId);
    if (!asset) return;

    setPosterFilePath(asset.file_path);
    setPosterAssetId(asset.id);
    setPosterMeta({
      filename: asset.asset_name,
      width: asset.width,
      height: asset.height,
      color_mode: asset.color_mode,
      format: asset.mime_type
    });
    setPosterPreviewUrl(api.getAssetFileUrl(asset.id));
    setIsDirty(true);
  };

  const handleRemovePoster = () => {
    setPosterFilePath(null);
    setPosterAssetId(null);
    setPosterAltText('');
    setPosterPreviewUrl(null);
    setPosterMeta(null);
    setIsDirty(true);
  };

  const saveDraftInternal = async (): Promise<ContentItem | null> => {
    const trimmedTitle = title.trim();
    const trimmedBody = bodyText.trim();
    if (!trimmedTitle || !trimmedBody) {
      alert('Please provide title and content text before saving or running checks.');
      return null;
    }
    const brandIdToUse = selectedBrandId || (brands.length > 0 ? brands[0].id : '');
    if (!brandIdToUse && !selectedContent) {
      alert('Please select a brand.');
      return null;
    }

    setSaving(true);
    try {
      let savedItem: ContentItem;
      if (selectedContent) {
        savedItem = await api.updateContentItem(
          selectedContent.id,
          trimmedBody,
          trimmedTitle,
          channel,
          posterFilePath || undefined,
          posterAssetId || undefined,
          posterAltText ? posterAltText.trim() : undefined
        );
      } else {
        savedItem = await api.createContentItem(
          brandIdToUse,
          trimmedTitle,
          channel,
          trimmedBody,
          posterFilePath || undefined,
          posterAssetId || undefined,
          posterAltText ? posterAltText.trim() : undefined
        );
      }

      // Synchronize editor state with the exact persisted version
      setSelectedContent(savedItem);
      setTitle(savedItem.title);
      setChannel(savedItem.channel);
      setSelectedBrandId(savedItem.brand_id);
      setBodyText(savedItem.latest_version?.body_text || '');

      const ver = savedItem.latest_version;
      if (ver && ver.poster_file_path) {
        setPosterFilePath(ver.poster_file_path);
        setPosterAssetId(ver.poster_asset_id || null);
        setPosterAltText(ver.poster_alt_text || '');
        setPosterPreviewUrl(api.getPosterUrl(ver.id));
        setPosterMeta({
          filename: ver.poster_file_path.split(/[/\\]/).pop()
        });
      } else {
        setPosterFilePath(null);
        setPosterAssetId(null);
        setPosterAltText('');
        setPosterPreviewUrl(null);
        setPosterMeta(null);
      }

      // Reload version history for the draft
      try {
        const vers = await api.getContentVersions(savedItem.id);
        setVersions(vers);
      } catch (err) {
        console.error('Failed to load version history after save:', err);
      }

      // Reload content items list
      try {
        const items = await api.getContentItems();
        setContentList(items);
      } catch (err) {
        console.error('Failed to reload content items after save:', err);
      }

      return savedItem;
    } catch (err: any) {
      alert(`Save error: ${err.message}`);
      return null;
    } finally {
      setSaving(false);
    }
  };

  const handleSaveDraft = async () => {
    if (saving || checking) return;
    const saved = await saveDraftInternal();
    if (saved) {
      setIsDirty(false);
    }
  };

  const handleRunChecks = async () => {
    if (saving || checking) return;

    setGovError(null);
    setChecking(true);
    try {
      // 1-3. Persist current editor state and retrieve exact persisted version
      const saved = await saveDraftInternal();
      if (!saved || !saved.latest_version) {
        setGovError('Draft save failed. Governance check was aborted.');
        setLatestGovRun(null);
        setCheckedVersionId(null);
        setCheckedVersionNum(null);
        return;
      }

      const targetVersionId = saved.latest_version.id;
      const targetVersionNum = saved.latest_version.version_num;

      // 4-5. Run governance against that exact version ID
      try {
        const run = await api.runGovernanceCheck(targetVersionId);
        setLatestGovRun(run);
        setCheckedVersionId(targetVersionId);
        setCheckedVersionNum(targetVersionNum);
        setIsDirty(false);
        const sugMap: Record<string, CorrectionSuggestion> = {};
        if (run.findings) {
          run.findings.forEach(f => {
            if (f.suggestion) sugMap[f.id] = f.suggestion;
          });
        }
        setSuggestions(sugMap);
        setSuggestionBanner(null);
      } catch (err: any) {
        // 8. If governance fails, show clear error and clear any stale results
        setGovError(`Governance check failed: ${err.message}`);
        setLatestGovRun(null);
        setCheckedVersionId(null);
        setCheckedVersionNum(null);
        setSuggestions({});
        alert(`Governance check error: ${err.message}`);
      }
    } finally {
      setChecking(false);
    }
  };

  // Milestone 5D: Suggestion Action Handlers
  const handleAcceptSuggestion = async (sug: CorrectionSuggestion) => {
    if (suggestionApplying || isDirty) {
      if (isDirty) {
        alert('You have unsaved edits in the copy editor. Please save or run governance checks first.');
      }
      return;
    }
    setSuggestionApplying(true);
    try {
      const res = await api.acceptSuggestion(sug.id);
      setSuggestions(prev => ({
        ...prev,
        [sug.finding_id]: res.suggestion
      }));

      if (res.applied_to_text) {
        setSuggestionBanner({
          type: 'success',
          text: `Applied correction! Created version v${res.new_version_num}. Governance results for prior version invalidated; please click "Run Governance Check" to evaluate.`
        });
        if (selectedContent) {
          const freshItem = await api.getContentItem(selectedContent.id);
          await selectDraft(freshItem);
        }
      } else {
        setSuggestionBanner({
          type: 'info',
          text: res.message
        });
      }
    } catch (err: any) {
      setSuggestionBanner({
        type: 'error',
        text: `Failed to accept suggestion: ${err.message}`
      });
      alert(`Failed to accept suggestion: ${err.message}`);
    } finally {
      setSuggestionApplying(false);
    }
  };

  const handleRejectSuggestion = async (sug: CorrectionSuggestion) => {
    if (suggestionApplying) return;
    setSuggestionApplying(true);
    try {
      const rejected = await api.rejectSuggestion(sug.id);
      setSuggestions(prev => ({
        ...prev,
        [sug.finding_id]: rejected
      }));
      setSuggestionBanner({
        type: 'info',
        text: 'Suggestion rejected. Content and finding remain unchanged.'
      });
    } catch (err: any) {
      alert(`Failed to reject suggestion: ${err.message}`);
    } finally {
      setSuggestionApplying(false);
    }
  };

  const handleOpenCustomEdit = (sug: CorrectionSuggestion) => {
    setActiveSuggestionForEdit(sug);
    setCustomEditText(sug.proposed_text || sug.original_text || '');
    setCustomEditModalOpen(true);
  };

  const handleApplyCustomEdit = async () => {
    if (!activeSuggestionForEdit || suggestionApplying || !customEditText.trim()) return;
    setSuggestionApplying(true);
    try {
      const res = await api.applyCustomSuggestion(activeSuggestionForEdit.id, customEditText.trim());
      setSuggestions(prev => ({
        ...prev,
        [activeSuggestionForEdit.finding_id]: res.suggestion
      }));
      setCustomEditModalOpen(false);
      setActiveSuggestionForEdit(null);
      setSuggestionBanner({
        type: 'success',
        text: `Custom correction applied! Created version v${res.new_version_num}. Please re-run governance check.`
      });
      if (selectedContent) {
        const freshItem = await api.getContentItem(selectedContent.id);
        await selectDraft(freshItem);
      }
    } catch (err: any) {
      alert(`Failed to apply custom edit: ${err.message}`);
    } finally {
      setSuggestionApplying(false);
    }
  };

  const handleSubmitForApproval = async () => {
    if (saving || checking || submitting) return;
    if (!selectedContent?.latest_version) return;
    if (isDirty) {
      alert('You have unsaved changes in the editor. Please save draft or run governance checks before submitting.');
      return;
    }
    setSubmitting(true);
    try {
      await api.submitForApproval(selectedContent.id, selectedContent.latest_version.id, submitNotes);
      setSubmitModalOpen(false);
      setSubmitNotes('');
      alert('Content version successfully submitted for human approval!');
      await loadContents();
      if (selectedContent) {
        const refreshed = await api.getContentItem(selectedContent.id);
        await selectDraft(refreshed);
      }
    } catch (err: any) {
      alert(`Submission error: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  // Filter findings
  const allFindings = latestGovRun?.findings || [];
  
  // Page filter (all | caption | page_number)
  const pageFilteredFindings = isPdf && pageFilter !== 'all'
    ? (pageFilter === 'caption'
        ? allFindings.filter(f => f.page_number === null || f.page_number === undefined)
        : allFindings.filter(f => f.page_number === pageFilter))
    : allFindings;

  const textFindings = pageFilteredFindings.filter(f =>
    !['dimensions', 'colour', 'contrast', 'logo', 'accessibility', 'layout'].includes(f.category)
  );
  const visualFindings = pageFilteredFindings.filter(f =>
    ['dimensions', 'colour', 'contrast', 'logo', 'accessibility', 'layout'].includes(f.category)
  );

  const displayedFindings = findingsFilter === 'text'
    ? textFindings
    : (findingsFilter === 'visual' ? visualFindings : pageFilteredFindings);

  return (
    <div>
      {/* Studio Header */}
      <div className="flex-between" style={{ marginBottom: 20 }}>
        <div>
          <h1 className="title-xl">Content Studio & Unified Governance</h1>
          <p className="text-sub">
            Author marketing copy, attach poster creatives, evaluate unified text and visual brand rules, and lock immutable versions for approval.
          </p>
        </div>
        <button id="new-draft-btn" onClick={handleCreateNewDraft} className="btn btn-secondary">
          <Plus size={16} /> New Draft
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '270px 1fr 420px', gap: 20, height: 'calc(100vh - 170px)' }}>
        {/* Left Column: Drafts & Revisions List */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', padding: 14, overflowY: 'auto' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Drafts & Submissions
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, overflowY: 'auto' }}>
            {contentList.map((item) => {
              const isSelected = selectedContent?.id === item.id;
              const hasPoster = Boolean(item.latest_version?.poster_file_path);
              return (
                <div
                  key={item.id}
                  onClick={() => selectDraft(item)}
                  style={{
                    padding: 12,
                    borderRadius: 8,
                    background: isSelected ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                    border: isSelected ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid var(--border-subtle)',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.875rem', color: isSelected ? '#fff' : 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 160 }}>
                      {item.title}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      {hasPoster && (
                        <span title="Poster attached" style={{ color: '#38bdf8' }}>
                          <ImageIcon size={12} />
                        </span>
                      )}
                      <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: 4, background: 'rgba(255,255,255,0.08)', color: '#cbd5e1' }}>
                        v{item.current_version_num}
                      </span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                    <StatusBadge status={item.status} />
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>{item.channel}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Version History Sub-Panel */}
          {selectedContent && versions.length > 0 && (
            <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#a5b4fc', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <History size={14} /> Immutable Version History
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 150, overflowY: 'auto' }}>
                {versions.map((ver) => (
                  <div key={ver.id} style={{ fontSize: '0.72rem', padding: '6px 8px', borderRadius: 6, background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600, color: '#fff' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        Version {ver.version_num}
                        {ver.poster_file_path && <ImageIcon size={10} color="#38bdf8" />}
                      </span>
                      <span style={{ color: 'var(--text-dim)' }}>{new Date(ver.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <div style={{ color: 'var(--text-dim)', fontFamily: 'monospace', fontSize: '0.65rem', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      sha256: {ver.checksum.slice(0, 16)}...
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Center Column: Copy Editor & Poster Creative */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', padding: 20, overflowY: 'auto' }}>
          <div style={{ display: 'flex', gap: 14, marginBottom: 14 }}>
            <div style={{ flex: 1 }}>
              <label className="form-label">Draft Title</label>
              <input
                id="draft-title-input"
                type="text"
                value={title}
                onChange={(e) => {
                  setTitle(e.target.value);
                  setIsDirty(true);
                }}
                className="input"
                placeholder="Campaign / Social post headline"
              />
            </div>
            {brands.length > 0 && (
              <div style={{ width: 150 }}>
                <label className="form-label">Brand</label>
                <select
                  value={selectedBrandId}
                  onChange={(e) => {
                    setSelectedBrandId(e.target.value);
                    setIsDirty(true);
                  }}
                  className="select"
                >
                  {brands.map((b) => (
                    <option key={b.id} value={b.id}>{b.name}</option>
                  ))}
                </select>
              </div>
            )}
            <div style={{ width: 170 }}>
              <label className="form-label">Target Channel</label>
              <select
                value={channel}
                onChange={(e) => {
                  setChannel(e.target.value);
                  setIsDirty(true);
                }}
                className="select"
              >
                <option value="Instagram Post">Instagram Post (1:1)</option>
                <option value="Instagram Story">Instagram Story (9:16)</option>
                <option value="Social Media">Social Media (General)</option>
                <option value="Website Banner">Website Banner (16:9)</option>
                <option value="Print Ad">Print Ad (CMYK)</option>
              </select>
            </div>
          </div>

          {/* Copy Editor */}
          <div style={{ display: 'flex', flexDirection: 'column', marginBottom: 16 }}>
            <div className="flex-between" style={{ marginBottom: 6 }}>
              <label className="form-label">Marketing Copy Text</label>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                {bodyText.length} characters | Deterministic rule & claim checks
              </span>
            </div>
            <textarea
              id="marketing-copy-textarea"
              value={bodyText}
              onChange={(e) => {
                setBodyText(e.target.value);
                setIsDirty(true);
              }}
              className="textarea"
              placeholder="Draft promotional text here. Evaluated against approved terminology, mandatory disclosures, and product facts..."
              style={{ minHeight: 140, fontSize: '0.92rem', lineHeight: 1.5 }}
            />
          </div>

          {/* Poster & Visual Asset Attachment Panel */}
          <div style={{
            padding: 14,
            borderRadius: 10,
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid var(--border-subtle)',
            marginBottom: 16
          }}>
            <div className="flex-between" style={{ marginBottom: 10 }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#93c5fd', display: 'flex', alignItems: 'center', gap: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                <ImageIcon size={15} /> {isPdf ? `Multi-Page Creative Deck (PDF) — ${pdfPageCount} ${pdfPageCount === 1 ? 'Page' : 'Pages'}` : 'Advertisement Creative Poster'}
              </div>
              {posterFilePath && (
                <button
                  type="button"
                  onClick={handleRemovePoster}
                  className="btn btn-secondary"
                  style={{ padding: '3px 8px', fontSize: '0.72rem', color: '#fb7185' }}
                >
                  <Trash2 size={12} /> Remove
                </button>
              )}
            </div>

            {!posterFilePath ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{
                  border: '2px dashed rgba(255,255,255,0.12)',
                  borderRadius: 8,
                  padding: '18px 14px',
                  textAlign: 'center',
                  background: 'rgba(0,0,0,0.2)',
                  cursor: 'pointer'
                }} onClick={() => fileInputRef.current?.click()}>
                  <Upload size={24} color="#818cf8" style={{ margin: '0 auto 6px auto' }} />
                  <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#e2e8f0' }}>
                    {uploadingPoster ? 'Uploading creative...' : 'Upload PDF Deck or Poster'}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 2 }}>
                    Supports PDF (up to 30 pages), PNG, JPG, or WEBP up to 25MB.
                  </div>
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileUpload}
                    accept="image/png,image/jpeg,image/webp,application/pdf"
                    style={{ display: 'none' }}
                  />
                </div>

                {assets.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>Or attach asset:</span>
                    <select
                      className="select"
                      style={{ fontSize: '0.75rem', padding: '4px 8px' }}
                      onChange={(e) => e.target.value && handleSelectBrandAsset(e.target.value)}
                      defaultValue=""
                    >
                      <option value="" disabled>Choose from Brand Assets...</option>
                      {assets.map(a => (
                        <option key={a.id} value={a.id}>
                          {a.asset_name} ({a.asset_type.replace('_', ' ')})
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {/* PDF Page Navigation Selector if Multi-Page PDF */}
                {isPdf && pdfPageCount > 1 && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 8px',
                    borderRadius: 6,
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.06)',
                    overflowX: 'auto'
                  }}>
                    <span style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginRight: 4 }}>
                      Pages:
                    </span>
                    {Array.from({ length: pdfPageCount }, (_, i) => i + 1).map((pgNum) => {
                      const isCur = selectedPage === pgNum;
                      const pgFindings = allFindings.filter(f => f.page_number === pgNum && f.status !== 'passed_check');
                      const hasCritical = pgFindings.some(f => f.severity === 'critical');
                      const hasWarn = pgFindings.some(f => f.severity === 'warning');
                      const hasPassed = allFindings.some(f => f.page_number === pgNum && f.status === 'passed_check');
                      const dotColor = hasCritical ? '#fb7185' : (hasWarn ? '#fbbf24' : (hasPassed ? '#34d399' : '#94a3b8'));

                      return (
                        <button
                          key={pgNum}
                          type="button"
                          onClick={() => handlePageSelect(pgNum)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 5,
                            padding: '3px 8px',
                            borderRadius: 4,
                            border: isCur ? '1px solid #6366f1' : '1px solid rgba(255,255,255,0.1)',
                            background: isCur ? 'rgba(99, 102, 241, 0.25)' : 'rgba(255,255,255,0.04)',
                            color: isCur ? '#fff' : 'var(--text-muted)',
                            fontSize: '0.72rem',
                            fontWeight: isCur ? 700 : 500,
                            cursor: 'pointer',
                            whiteSpace: 'nowrap'
                          }}
                        >
                          <span style={{ width: 6, height: 6, borderRadius: '50%', background: dotColor }} />
                          Page {pgNum}
                        </button>
                      );
                    })}
                  </div>
                )}

                <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
                  {posterPreviewUrl ? (
                    <div style={{ position: 'relative' }}>
                      <img
                        src={posterPreviewUrl}
                        alt={posterAltText || (isPdf ? `Page ${selectedPage} preview` : 'Poster preview')}
                        style={{
                          width: 100,
                          height: 100,
                          objectFit: 'contain',
                          borderRadius: 8,
                          background: '#090d16',
                          border: '1px solid rgba(255,255,255,0.15)'
                        }}
                        onError={(e) => {
                          (e.target as HTMLElement).style.display = 'none';
                        }}
                      />
                      {isPdf && (
                        <span style={{
                          position: 'absolute',
                          bottom: 4,
                          right: 4,
                          background: 'rgba(0,0,0,0.75)',
                          color: '#fff',
                          fontSize: '0.62rem',
                          padding: '1px 4px',
                          borderRadius: 3,
                          fontWeight: 700
                        }}>
                          p. {selectedPage}/{pdfPageCount}
                        </span>
                      )}
                    </div>
                  ) : (
                    <div style={{
                      width: 100,
                      height: 100,
                      borderRadius: 8,
                      background: 'rgba(99, 102, 241, 0.1)',
                      border: '1px solid rgba(99, 102, 241, 0.3)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}>
                      <ImageIcon size={32} color="#818cf8" />
                    </div>
                  )}

                  <div style={{ flex: 1, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.85rem' }}>
                      {posterMeta?.filename || (isPdf ? `PDF Creative Deck (${pdfPageCount} Pages)` : 'Creative Asset Attached')}
                    </div>
                    {isPdf && pdfPages[selectedPage - 1] && (
                      <div style={{ marginTop: 2 }}>
                        Page {selectedPage}: <strong>{pdfPages[selectedPage - 1].width_px}x{pdfPages[selectedPage - 1].height_px}px</strong> ({pdfPages[selectedPage - 1].orientation})
                      </div>
                    )}
                    {!isPdf && posterMeta?.width && posterMeta?.height && (
                      <div style={{ marginTop: 2 }}>
                        Resolution: <strong>{posterMeta.width}x{posterMeta.height}px</strong> ({posterMeta.color_mode || 'RGB'})
                      </div>
                    )}
                    <div style={{ fontSize: '0.7rem', color: '#34d399', marginTop: 4 }}>
                      ✓ {isPdf ? `Page-level text, facts and visual governance evaluated across all ${pdfPageCount} pages` : 'Visual governance checks will run automatically with text'}
                    </div>
                  </div>
                </div>

                {/* Alt-Text Input */}
                <div>
                  <div className="flex-between" style={{ marginBottom: 4 }}>
                    <label className="form-label" style={{ fontSize: '0.75rem', marginBottom: 0 }}>
                      {isPdf ? 'Creative Deck Summary / Alternative Text (Accessibility)' : 'Alternative Text (Alt-Text Accessibility)'}
                    </label>
                    <span style={{ fontSize: '0.7rem', color: posterAltText.length >= 10 ? '#34d399' : '#fbbf24' }}>
                      {posterAltText.length} chars {posterAltText.length < 10 ? '(min 10 required)' : '✓'}
                    </span>
                  </div>
                  <input
                    type="text"
                    value={posterAltText}
                    onChange={(e) => {
                      setPosterAltText(e.target.value);
                      setIsDirty(true);
                    }}
                    className="input"
                    placeholder={isPdf ? "Describe the overall carousel or presentation deck content..." : "Describe the image content and visual text for screen-reader accessibility..."}
                    style={{ fontSize: '0.82rem', padding: '6px 10px' }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Action Bar */}
          <div className="flex-between" style={{
            marginTop: 'auto',
            paddingTop: 12,
            paddingBottom: 4,
            borderTop: '1px solid var(--border-subtle)',
            position: 'sticky',
            bottom: -20,
            background: 'var(--card-bg, #131b2e)',
            zIndex: 10
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {selectedContent && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                  Current Version: <strong>v{selectedContent.current_version_num}</strong> | Status: <StatusBadge status={selectedContent.status} />
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                id="save-draft-btn"
                onClick={handleSaveDraft}
                disabled={saving || checking}
                className="btn btn-secondary"
              >
                {saving ? 'Saving...' : 'Save Draft Revision'}
              </button>
              <button
                id="run-governance-btn"
                onClick={handleRunChecks}
                disabled={saving || checking}
                className="btn btn-primary"
              >
                <Play size={16} /> {checking ? 'Evaluating...' : 'Run Governance Check'}
              </button>
              {selectedContent && isCreator && selectedContent.status !== 'approved' && (
                <button
                  id="submit-approval-btn"
                  onClick={() => setSubmitModalOpen(true)}
                  disabled={saving || checking || submitting}
                  className="btn btn-success"
                >
                  <Send size={16} /> Submit for Approval
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Unified Explainable Governance Findings */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', padding: 18, overflowY: 'auto' }}>
          <div className="flex-between" style={{ marginBottom: 12 }}>
            <div>
              <h2 className="title-md" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Sparkles size={18} color="#818cf8" /> Unified Governance
              </h2>
              {latestGovRun && checkedVersionNum && (
                <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 2 }}>
                  Evaluated on <strong>Version {checkedVersionNum}</strong>
                  {checkedVersionId && <span style={{ fontFamily: 'monospace', marginLeft: 4 }}>({checkedVersionId.slice(0, 8)})</span>}
                </div>
              )}
            </div>
            {latestGovRun && (
              <span className={`badge badge-${latestGovRun.overall_status === 'passed' ? 'success' : (latestGovRun.overall_status === 'warnings' ? 'warning' : 'danger')}`}>
                {latestGovRun.overall_status.toUpperCase()}
              </span>
            )}
          </div>

          {/* Actionable Error Banner if save or check failed */}
          {govError && (
            <div style={{
              padding: '10px 12px',
              borderRadius: 8,
              background: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              color: '#fca5a5',
              fontSize: '0.78rem',
              marginBottom: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}>
              <XCircle size={16} color="#f87171" style={{ flexShrink: 0 }} />
              <div>
                <strong>Execution Error:</strong> {govError}
              </div>
            </div>
          )}

          {/* Stale Findings / Unsaved Changes Warning Banner */}
          {latestGovRun && isDirty && (
            <div
              id="content-modified-banner"
              style={{
                padding: '10px 12px',
                borderRadius: 8,
                background: 'rgba(245, 158, 11, 0.12)',
                border: '1px solid rgba(245, 158, 11, 0.4)',
                color: '#fcd34d',
                fontSize: '0.78rem',
                marginBottom: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 8
              }}
            >
              <AlertTriangle size={16} color="#fbbf24" style={{ flexShrink: 0 }} />
              <div>
                <strong>Content Modified:</strong> The editor has unsaved changes. Findings below belong to <strong>v{checkedVersionNum}</strong>. Run Governance Checks to evaluate the current revision.
              </div>
            </div>
          )}

          {/* Multi-Page PDF Analysis vs Compliance Distinction Banner */}
          {isPdf && latestGovRun && (
            (() => {
              const pagesWithIssues = new Set(
                allFindings
                  .filter(f => f.page_number !== null && f.page_number !== undefined && f.status !== 'passed_check')
                  .map(f => f.page_number)
              );
              const hasBlockers = allFindings.some(f => f.severity === 'critical' && f.status !== 'passed_check');
              const hasWarnings = allFindings.some(f => f.severity === 'warning' && f.status !== 'passed_check');
              const allCompliant = pagesWithIssues.size === 0 && !hasBlockers && !hasWarnings;

              return (
                <div style={{
                  padding: '10px 12px',
                  borderRadius: 8,
                  marginBottom: 12,
                  background: allCompliant ? 'rgba(16, 185, 129, 0.12)' : 'rgba(99, 102, 241, 0.12)',
                  border: `1px solid ${allCompliant ? 'rgba(16, 185, 129, 0.4)' : 'rgba(99, 102, 241, 0.4)'}`,
                  fontSize: '0.78rem'
                }}>
                  <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6, color: allCompliant ? '#34d399' : '#a5b4fc', marginBottom: 3 }}>
                    {allCompliant ? <CheckCircle size={15} /> : <AlertTriangle size={15} />}
                    {allCompliant
                      ? `All ${pdfPageCount} Pages Analysed & Compliant`
                      : `All ${pdfPageCount} Pages Analysed (${pagesWithIssues.size} With Findings)`}
                  </div>
                  <div style={{ color: 'var(--text-dim)', fontSize: '0.72rem', lineHeight: 1.3 }}>
                    {allCompliant
                      ? 'Every page in this PDF creative conforms to brand specifications and fact checks.'
                      : 'Note: "All pages analysed" does not equal "All pages compliant". Inspect individual page findings below.'}
                  </div>
                </div>
              );
            })()
          )}

          {/* Multi-Page PDF Page-Level Finding Filter Selector */}
          {isPdf && latestGovRun && pdfPageCount > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: 6 }}>
                Filter By PDF Page / Caption
              </div>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() => setPageFilter('all')}
                  style={{
                    padding: '3px 8px',
                    borderRadius: 4,
                    border: pageFilter === 'all' ? '1px solid #6366f1' : '1px solid rgba(255,255,255,0.1)',
                    background: pageFilter === 'all' ? '#4f46e5' : 'rgba(255,255,255,0.04)',
                    color: '#fff',
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  All Pages ({allFindings.length})
                </button>
                {Array.from({ length: pdfPageCount }, (_, i) => i + 1).map((p) => {
                  const pFindings = allFindings.filter(f => f.page_number === p);
                  const pIssues = pFindings.filter(f => f.status !== 'passed_check');
                  const hasCrit = pIssues.some(f => f.severity === 'critical');
                  const hasWarn = pIssues.some(f => f.severity === 'warning');
                  const isCur = pageFilter === p;
                  const dotColor = hasCrit ? '#fb7185' : (hasWarn ? '#fbbf24' : (pFindings.length > 0 ? '#34d399' : '#94a3b8'));

                  return (
                    <button
                      key={p}
                      type="button"
                      onClick={() => {
                        setPageFilter(p);
                        setSelectedPage(p);
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                        padding: '3px 8px',
                        borderRadius: 4,
                        border: isCur ? '1px solid #6366f1' : '1px solid rgba(255,255,255,0.1)',
                        background: isCur ? '#4f46e5' : 'rgba(255,255,255,0.04)',
                        color: isCur ? '#fff' : 'var(--text-muted)',
                        fontSize: '0.72rem',
                        fontWeight: isCur ? 700 : 500,
                        cursor: 'pointer'
                      }}
                    >
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: dotColor }} />
                      Pg {p} ({pFindings.length})
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={() => setPageFilter('caption')}
                  style={{
                    padding: '3px 8px',
                    borderRadius: 4,
                    border: pageFilter === 'caption' ? '1px solid #6366f1' : '1px solid rgba(255,255,255,0.1)',
                    background: pageFilter === 'caption' ? '#4f46e5' : 'rgba(255,255,255,0.04)',
                    color: '#fff',
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  Caption ({allFindings.filter(f => f.page_number === null || f.page_number === undefined).length})
                </button>
              </div>
            </div>
          )}

          {/* Suggestion Feedback Banner */}
          {suggestionBanner && (
            <div style={{
              padding: '8px 12px',
              borderRadius: 6,
              marginBottom: 10,
              fontSize: '0.75rem',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: suggestionBanner.type === 'success'
                ? 'rgba(16, 185, 129, 0.15)'
                : (suggestionBanner.type === 'error' ? 'rgba(244, 63, 94, 0.15)' : 'rgba(56, 189, 248, 0.15)'),
              border: `1px solid ${suggestionBanner.type === 'success' ? '#10b981' : (suggestionBanner.type === 'error' ? '#f43f5e' : '#38bdf8')}`,
              color: '#fff'
            }}>
              {suggestionBanner.type === 'success' && <CheckCircle size={14} color="#34d399" />}
              {suggestionBanner.type === 'error' && <XCircle size={14} color="#fb7185" />}
              {suggestionBanner.type === 'info' && <Info size={14} color="#38bdf8" />}
              <span style={{ flex: 1 }}>{suggestionBanner.text}</span>
              <button
                type="button"
                onClick={() => setSuggestionBanner(null)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 0 }}
              >
                ×
              </button>
            </div>
          )}

          {/* Findings Filter Tabs */}
          {latestGovRun && (
            <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
              <button
                type="button"
                onClick={() => setFindingsFilter('all')}
                style={{
                  flex: 1,
                  padding: '5px 8px',
                  borderRadius: 6,
                  border: 'none',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: findingsFilter === 'all' ? '#4f46e5' : 'rgba(255,255,255,0.05)',
                  color: '#fff'
                }}
              >
                All Categories ({pageFilteredFindings.length})
              </button>
              <button
                type="button"
                onClick={() => setFindingsFilter('text')}
                style={{
                  flex: 1,
                  padding: '5px 8px',
                  borderRadius: 6,
                  border: 'none',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: findingsFilter === 'text' ? '#4f46e5' : 'rgba(255,255,255,0.05)',
                  color: '#fff'
                }}
              >
                Text ({textFindings.length})
              </button>
              <button
                type="button"
                onClick={() => setFindingsFilter('visual')}
                style={{
                  flex: 1,
                  padding: '5px 8px',
                  borderRadius: 6,
                  border: 'none',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: findingsFilter === 'visual' ? '#4f46e5' : 'rgba(255,255,255,0.05)',
                  color: '#fff'
                }}
              >
                Visual ({visualFindings.length})
              </button>
            </div>
          )}

          {!latestGovRun ? (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-dim)' }}>
              <ShieldAlert size={36} style={{ margin: '0 auto 12px auto', opacity: 0.4 }} />
              <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>No Governance Check Executed</div>
              <div style={{ fontSize: '0.78rem', marginTop: 4 }}>
                Click "Run Governance Check" to evaluate this text and attached creative against approved brand guidelines and specifications.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto' }}>
              {displayedFindings.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '30px 10px', background: 'rgba(16,185,129,0.08)', borderRadius: 10, border: '1px solid rgba(16,185,129,0.2)' }}>
                  <CheckCircle size={28} color="#34d399" style={{ margin: '0 auto 6px auto' }} />
                  <div style={{ fontWeight: 700, color: '#34d399', fontSize: '0.88rem' }}>No Issues in this Category</div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 2 }}>
                    Content conforms to checked brand requirements.
                  </div>
                </div>
              ) : (
                displayedFindings.map((f, idx) => {
                  const isPass = f.status === 'passed_check';
                  const isUnable = f.status === 'unable_to_verify';
                  const isIssue = !isPass && !isUnable;

                  const borderColor = isPass
                    ? 'rgba(16,185,129,0.25)'
                    : (isUnable ? 'rgba(168,85,247,0.25)' : (f.severity === 'critical' ? 'rgba(244,63,94,0.3)' : 'rgba(245,158,11,0.3)'));

                  const bgColor = isPass
                    ? 'rgba(16,185,129,0.05)'
                    : (isUnable ? 'rgba(168,85,247,0.06)' : (f.severity === 'critical' ? 'rgba(244,63,94,0.08)' : 'rgba(245,158,11,0.08)'));

                  return (
                    <div
                      key={f.id || idx}
                      style={{
                        padding: 12,
                        borderRadius: 8,
                        background: bgColor,
                        border: `1px solid ${borderColor}`,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                          {isPdf && (
                            f.page_number ? (
                              <button
                                type="button"
                                onClick={() => handlePageSelect(f.page_number!)}
                                style={{
                                  fontSize: '0.65rem',
                                  fontWeight: 700,
                                  padding: '1px 6px',
                                  borderRadius: 4,
                                  border: 'none',
                                  background: selectedPage === f.page_number ? '#6366f1' : 'rgba(99, 102, 241, 0.25)',
                                  color: '#fff',
                                  cursor: 'pointer'
                                }}
                                title={`Click to jump to Page ${f.page_number}`}
                              >
                                Page {f.page_number}
                              </button>
                            ) : (
                              <span style={{
                                fontSize: '0.65rem',
                                fontWeight: 600,
                                padding: '1px 5px',
                                borderRadius: 4,
                                background: 'rgba(255,255,255,0.06)',
                                color: '#94a3b8'
                              }}>
                                Caption
                              </span>
                            )
                          )}
                          <span style={{
                            fontSize: '0.65rem',
                            fontWeight: 700,
                            padding: '1px 5px',
                            borderRadius: 4,
                            background: 'rgba(255,255,255,0.08)',
                            color: '#93c5fd',
                            textTransform: 'uppercase'
                          }}>
                            {f.category}
                          </span>
                          <span style={{
                            fontWeight: 700,
                            fontSize: '0.82rem',
                            color: isPass ? '#34d399' : (isUnable ? '#c084fc' : (f.severity === 'critical' ? '#fb7185' : '#fbbf24'))
                          }}>
                            {f.title}
                          </span>
                        </div>

                        {/* Status / Severity Badge */}
                        <span style={{
                          fontSize: '0.65rem',
                          fontWeight: 700,
                          padding: '1px 6px',
                          borderRadius: 4,
                          whiteSpace: 'nowrap',
                          background: isPass ? 'rgba(16,185,129,0.2)' : (isUnable ? 'rgba(168,85,247,0.2)' : (f.severity === 'critical' ? 'rgba(244,63,94,0.2)' : 'rgba(245,158,11,0.2)')),
                          color: isPass ? '#34d399' : (isUnable ? '#d8b4fe' : (f.severity === 'critical' ? '#fb7185' : '#fcd34d'))
                        }}>
                          {isPass ? 'PASSED' : (isUnable ? 'UNVERIFIED' : f.severity.toUpperCase())}
                        </span>
                      </div>

                      <div style={{ fontSize: '0.78rem', color: '#e2e8f0', lineHeight: 1.4 }}>
                        {f.explanation}
                      </div>

                      {f.text_excerpt && (
                        <div style={{
                          padding: '4px 8px',
                          background: 'rgba(0,0,0,0.3)',
                          borderRadius: 4,
                          fontFamily: 'monospace',
                          fontSize: '0.7rem',
                          color: '#cbd5e1'
                        }}>
                          Measurement / Excerpt: "{f.text_excerpt}"
                        </div>
                      )}

                      <div style={{ fontSize: '0.7rem', marginTop: 2, paddingTop: 4, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                        <div style={{ color: 'var(--text-dim)' }}>
                          Source: <strong style={{ color: f.source_citation === 'SUPPORTING EVIDENCE NOT FOUND' ? '#fb7185' : '#818cf8' }}>
                            {f.source_citation}
                          </strong>
                        </div>
                        {f.recommended_action && f.recommended_action !== 'No change needed.' && (
                          <div style={{ color: '#38bdf8', marginTop: 2 }}>
                            Action: {f.recommended_action}
                          </div>
                        )}
                      </div>

                      {/* Milestone 5D: Context-Preserving Correction Suggestion */}
                      {(() => {
                        const sug = suggestions[f.id] || f.suggestion;
                        if (!sug) return null;

                        return (
                          <div style={{
                            marginTop: 8,
                            padding: '10px 12px',
                            borderRadius: 8,
                            background: 'rgba(99, 102, 241, 0.08)',
                            border: '1px solid rgba(99, 102, 241, 0.25)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 8
                          }}>
                            {/* Header */}
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: '0.78rem', color: '#a5b4fc' }}>
                                <Sparkles size={14} color="#818cf8" />
                                <span>Context-Preserving Correction</span>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{
                                  fontSize: '0.65rem',
                                  fontWeight: 700,
                                  padding: '1px 5px',
                                  borderRadius: 4,
                                  background: 'rgba(99, 102, 241, 0.2)',
                                  color: '#c7d2fe',
                                  textTransform: 'uppercase'
                                }}>
                                  {sug.correction_type.replace(/_/g, ' ')}
                                </span>
                                <span style={{
                                  fontSize: '0.65rem',
                                  fontWeight: 700,
                                  padding: '1px 6px',
                                  borderRadius: 4,
                                  background: sug.status === 'applied'
                                    ? 'rgba(16, 185, 129, 0.2)'
                                    : (sug.status === 'accepted'
                                      ? 'rgba(56, 189, 248, 0.2)'
                                      : (sug.status === 'rejected'
                                        ? 'rgba(148, 163, 184, 0.2)'
                                        : (sug.status === 'stale'
                                          ? 'rgba(245, 158, 11, 0.2)'
                                          : 'rgba(168, 85, 247, 0.2)'))),
                                  color: sug.status === 'applied'
                                    ? '#34d399'
                                    : (sug.status === 'accepted'
                                      ? '#38bdf8'
                                      : (sug.status === 'rejected'
                                        ? '#94a3b8'
                                        : (sug.status === 'stale'
                                          ? '#fbbf24'
                                          : '#d8b4fe')))
                                }}>
                                  {sug.status.toUpperCase()}
                                </span>
                              </div>
                            </div>

                            {/* Explanation */}
                            <div style={{ fontSize: '0.75rem', color: '#e2e8f0', lineHeight: 1.4 }}>
                              {sug.explanation}
                            </div>

                            {/* Diff Preview / Proposed Passage */}
                            {sug.diff_preview ? (
                              <div style={{
                                background: 'rgba(0,0,0,0.4)',
                                padding: '8px 10px',
                                borderRadius: 6,
                                fontFamily: 'monospace',
                                fontSize: '0.72rem',
                                lineHeight: 1.5,
                                whiteSpace: 'pre-wrap',
                                border: '1px solid rgba(255,255,255,0.06)'
                              }}>
                                {sug.diff_preview.split('\n').map((line, lIdx) => (
                                  <div key={lIdx} style={{
                                    color: line.startsWith('+') ? '#34d399' : (line.startsWith('-') ? '#fb7185' : '#cbd5e1'),
                                    fontWeight: (line.startsWith('+') || line.startsWith('-')) ? 600 : 400
                                  }}>
                                    {line}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              sug.proposed_text && (
                                <div style={{
                                  background: 'rgba(0,0,0,0.4)',
                                  padding: '6px 10px',
                                  borderRadius: 6,
                                  fontFamily: 'monospace',
                                  fontSize: '0.72rem',
                                  color: '#34d399'
                                }}>
                                  Proposed: "{sug.proposed_text}"
                                </div>
                              )
                            )}

                            {/* Evidence Citation */}
                            <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>
                              Supporting Evidence: <span style={{ color: '#93c5fd' }}>{sug.evidence_source}</span>
                            </div>

                            {/* Artwork notice if not body text */}
                            {sug.target_type !== 'body_text' && (
                              <div style={{
                                padding: '4px 8px',
                                borderRadius: 4,
                                background: 'rgba(245, 158, 11, 0.1)',
                                border: '1px solid rgba(245, 158, 11, 0.25)',
                                fontSize: '0.68rem',
                                color: '#fcd34d',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6
                              }}>
                                <Info size={12} />
                                <span>Artwork Notice: This creative asset cannot be modified directly via text replacement. Update in authoring tool and re-upload.</span>
                              </div>
                            )}

                            {/* Staleness Notice */}
                            {(sug.status === 'stale' || isDirty) && (
                              <div style={{
                                padding: '4px 8px',
                                borderRadius: 4,
                                background: 'rgba(245, 158, 11, 0.12)',
                                border: '1px solid rgba(245, 158, 11, 0.3)',
                                fontSize: '0.68rem',
                                color: '#fbbf24',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6
                              }}>
                                <AlertTriangle size={12} />
                                <span>Draft modified since check. Re-run governance check to refresh suggestions.</span>
                              </div>
                            )}

                            {/* Action Buttons if pending */}
                            {sug.status === 'pending' && !isDirty && (
                              <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                                {sug.can_auto_apply ? (
                                  <>
                                    <button
                                      type="button"
                                      disabled={suggestionApplying}
                                      onClick={() => handleAcceptSuggestion(sug)}
                                      style={{
                                        padding: '4px 10px',
                                        borderRadius: 5,
                                        border: 'none',
                                        background: '#4f46e5',
                                        color: '#fff',
                                        fontSize: '0.72rem',
                                        fontWeight: 600,
                                        cursor: 'pointer',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 4
                                      }}
                                    >
                                      <Sparkles size={12} />
                                      Accept & Create Revision
                                    </button>
                                    <button
                                      type="button"
                                      disabled={suggestionApplying}
                                      onClick={() => handleOpenCustomEdit(sug)}
                                      style={{
                                        padding: '4px 8px',
                                        borderRadius: 5,
                                        border: '1px solid rgba(255,255,255,0.15)',
                                        background: 'rgba(255,255,255,0.05)',
                                        color: '#e2e8f0',
                                        fontSize: '0.72rem',
                                        cursor: 'pointer'
                                      }}
                                    >
                                      Edit Before Applying
                                    </button>
                                  </>
                                ) : (
                                  <button
                                    type="button"
                                    disabled={suggestionApplying}
                                    onClick={() => handleAcceptSuggestion(sug)}
                                    style={{
                                      padding: '4px 10px',
                                      borderRadius: 5,
                                      border: '1px solid rgba(56, 189, 248, 0.4)',
                                      background: 'rgba(56, 189, 248, 0.15)',
                                      color: '#38bdf8',
                                      fontSize: '0.72rem',
                                      fontWeight: 600,
                                      cursor: 'pointer'
                                    }}
                                  >
                                    Acknowledge Guidance
                                  </button>
                                )}
                                <button
                                  type="button"
                                  disabled={suggestionApplying}
                                  onClick={() => handleRejectSuggestion(sug)}
                                  style={{
                                    padding: '4px 8px',
                                    borderRadius: 5,
                                    border: '1px solid rgba(255,255,255,0.08)',
                                    background: 'transparent',
                                    color: '#94a3b8',
                                    fontSize: '0.72rem',
                                    cursor: 'pointer'
                                  }}
                                >
                                  Reject
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      })()}
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>

      {/* Submit for Approval Modal */}
      {submitModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100
        }}>
          <div className="card" style={{ width: 460, background: '#131b2e', border: '1px solid rgba(255,255,255,0.15)' }}>
            <h2 className="title-md" style={{ marginBottom: 12 }}>
              Submit for Human Approval
            </h2>
            <p className="text-sub" style={{ marginBottom: 14 }}>
              This will lock <strong>Version {selectedContent?.current_version_num}</strong> with immutable checksum:
              <br />
              <code style={{ fontSize: '0.7rem', color: '#a5b4fc' }}>
                {selectedContent?.latest_version?.checksum.slice(0, 24)}...
              </code>
              {selectedContent?.latest_version?.poster_file_path && (
                <span style={{ display: 'block', fontSize: '0.75rem', color: '#38bdf8', marginTop: 4 }}>
                  ✓ Includes attached creative poster in locked version bundle
                </span>
              )}
            </p>

            <div className="form-group">
              <label className="form-label">Submission Notes for Approval Manager</label>
              <textarea
                value={submitNotes}
                onChange={(e) => setSubmitNotes(e.target.value)}
                className="textarea"
                placeholder="e.g., Reviewed against Q4 guidelines. All medical claims removed, poster contrast and brand colors verified."
                style={{ minHeight: 80 }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
              <button onClick={() => setSubmitModalOpen(false)} className="btn btn-secondary">
                Cancel
              </button>
              <button onClick={handleSubmitForApproval} disabled={submitting} className="btn btn-success">
                {submitting ? 'Submitting...' : 'Confirm Submission'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Custom Edit Suggestion Modal */}
      {customEditModalOpen && activeSuggestionForEdit && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 110
        }}>
          <div className="card" style={{ width: 520, background: '#131b2e', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Sparkles size={16} color="#818cf8" />
              Customize Correction Before Applying
            </h3>
            <p className="text-sub" style={{ marginBottom: 12 }}>
              Fine-tune the replacement copy for <strong>{activeSuggestionForEdit.rule_code || 'finding'}</strong>. Applying this will create a new immutable draft revision.
            </p>

            <div style={{ marginBottom: 12 }}>
              <label className="form-label">Original Text Excerpt</label>
              <div style={{
                padding: '6px 10px',
                borderRadius: 6,
                background: 'rgba(0,0,0,0.3)',
                fontFamily: 'monospace',
                fontSize: '0.75rem',
                color: '#fb7185',
                border: '1px solid rgba(244,63,94,0.2)'
              }}>
                "{activeSuggestionForEdit.original_text}"
              </div>
            </div>

            <div style={{ marginBottom: 14 }}>
              <label className="form-label">Your Custom Replacement</label>
              <textarea
                className="textarea"
                rows={3}
                value={customEditText}
                onChange={(e) => setCustomEditText(e.target.value)}
                placeholder="Enter custom replacement copy..."
                style={{ width: '100%', fontFamily: 'inherit', fontSize: '0.82rem' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setCustomEditModalOpen(false);
                  setActiveSuggestionForEdit(null);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleApplyCustomEdit}
                disabled={suggestionApplying || !customEditText.trim()}
              >
                {suggestionApplying ? 'Applying...' : 'Apply & Create Revision'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
