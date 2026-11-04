import React, { useState, useEffect, useRef, useMemo } from 'react';
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
  HelpCircle,
  FolderOpen,
  Search,
  X,
  ChevronRight,
  Check,
  FileText
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { StatusBadge } from '../components/StatusBadge';
import { GovernanceReviewPanel } from '../components/GovernanceReviewPanel';
import { ContentItem, ContentVersion, GovernanceRun, Brand, BrandAsset, CorrectionSuggestion } from '../types';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

export type ContentType = 'image' | 'text' | 'both';

export const ContentStudio: React.FC = () => {
  const { role } = useAuth();
  const [contentList, setContentList] = useState<ContentItem[]>([]);
  const [selectedContent, setSelectedContent] = useState<ContentItem | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [assets, setAssets] = useState<BrandAsset[]>([]);
  const [versions, setVersions] = useState<ContentVersion[]>([]);
  const [latestGovRun, setLatestGovRun] = useState<GovernanceRun | null>(null);

  // Content Type & Form Editor State
  const [contentType, setContentType] = useState<ContentType>('both');
  const [title, setTitle] = useState('');
  const [channel, setChannel] = useState('General');
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

  // Round 3 Phase 2: Dynamic Product Selection & Real-Time In-Editor Assistant
  const [products, setProducts] = useState<any[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<string>('');
  const [liveInfractions, setLiveInfractions] = useState<any[]>([]);
  const [isLiveChecking, setIsLiveChecking] = useState(false);
  const [isRealTimeExpanded, setIsRealTimeExpanded] = useState(false);
  const liveCheckDebounceRef = useRef<any>(null);

  // Collapsible Drafts Drawer State
  const [draftsDrawerOpen, setDraftsDrawerOpen] = useState(false);
  const [draftSearchQuery, setDraftSearchQuery] = useState('');

  const isCreator = role === 'content_creator' || role === 'org_admin';

  // 600ms Debounced In-Editor Live Check
  useEffect(() => {
    if (!bodyText.trim()) {
      setLiveInfractions([]);
      return;
    }

    if (liveCheckDebounceRef.current) {
      clearTimeout(liveCheckDebounceRef.current);
    }

    liveCheckDebounceRef.current = setTimeout(async () => {
      setIsLiveChecking(true);
      try {
        const res = await api.liveCheck({
          brand_id: selectedBrandId || undefined,
          product_id: selectedProductId || undefined,
          channel,
          title,
          body_text: bodyText
        });
        setLiveInfractions(res.infractions || []);
      } catch (err) {
        console.warn('Real-time live check skipped:', err);
      } finally {
        setIsLiveChecking(false);
      }
    }, 600);

    return () => {
      if (liveCheckDebounceRef.current) {
        clearTimeout(liveCheckDebounceRef.current);
      }
    };
  }, [bodyText, selectedProductId, channel, selectedBrandId, title]);

  const applyLiveAutoFix = (inf: any) => {
    if (inf.matched_text && inf.replacement_text) {
      setBodyText(prev => prev.replace(inf.matched_text, inf.replacement_text));
      setIsDirty(true);
    } else if (inf.replacement_text && !inf.matched_text) {
      setBodyText(inf.replacement_text);
      setIsDirty(true);
    }
  };

  const isPollingRef = useRef(false);

  const loadContents = async (silent = false) => {
    if (silent && isPollingRef.current) return;
    if (silent) isPollingRef.current = true;
    try {
      if (!silent) {
        // Initial page load or manual refresh: fetch static catalogue data and content items
        const [items, b, a, prods] = await Promise.all([
          api.getContentItems(),
          api.getBrands(),
          api.getAssets(),
          api.getProducts().catch(() => [])
        ]);
        setContentList(items);
        setBrands(b);
        setAssets(a);
        setProducts(prods || []);
        if (b.length > 0 && !selectedBrandId) {
          setSelectedBrandId(b[0].id);
        }
        if (items.length > 0 && !selectedContent) {
          selectDraft(items[0]);
        }
      } else {
        // Background polling: fetch ONLY content items (lightweight draft enumeration)
        const items = await api.getContentItems();
        setContentList(items);
        if (selectedContent && !saving && !submitting && !checking) {
          const freshItem = items.find(i => i.id === selectedContent.id);
          if (freshItem) {
            setSelectedContent(freshItem);
            try {
              const vers = await api.getContentVersions(freshItem.id);
              setVersions(vers);
            } catch {
              // ignore version load error
            }
          }
        }
      }
    } catch (err) {
      console.error('Failed to load content items:', err);
      if (silent) throw err; // Propagate to useAutoRefresh so backoff delay engages
    } finally {
      if (silent) isPollingRef.current = false;
    }
  };

  useEffect(() => {
    loadContents(false);
  }, []);

  useAutoRefresh(() => {
    if (!saving && !submitting && !checking && !isDirty && !draftsDrawerOpen) {
      return loadContents(true);
    }
  }, { intervalMs: 30000 });

  const selectDraft = async (item: ContentItem) => {
    setSelectedContent(item);
    setTitle(item.title);
    setChannel(item.channel);
    setSelectedBrandId(item.brand_id);
    setSelectedProductId(item.product_id || '');
    setBodyText(item.latest_version?.body_text || '');
    setGovError(null);
    setIsDirty(false);

    // Determine content type from version details
    const ver = item.latest_version;
    const hasPoster = Boolean(ver && ver.poster_file_path);
    const hasText = Boolean(ver && ver.body_text && ver.body_text.trim().length > 0);
    if (hasPoster && hasText) {
      setContentType('both');
    } else if (hasPoster && !hasText) {
      setContentType('image');
    } else if (!hasPoster && hasText) {
      setContentType('text');
    } else {
      setContentType('both');
    }

    // Restore poster details from version
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

      // Load latest governance run for current version
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
    setContentType('both');
    setChannel('General');
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
    setSelectedProductId('');
    setVersions([]);
    if (brands.length > 0) {
      setSelectedBrandId(brands[0].id);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
      alert('PDF advertisement uploads are no longer supported. Please upload an image creative in PNG, JPG, or WEBP format.');
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    const MAX_UPLOAD_BYTES = 15 * 1024 * 1024; // 15 MB
    if (file.size > MAX_UPLOAD_BYTES) {
      alert('File size exceeds maximum allowed limit of 15 MB.');
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    const validExts = ['.png', '.jpg', '.jpeg', '.webp'];
    const validMimes = ['image/png', 'image/jpeg', 'image/webp'];
    const hasValidExt = validExts.some(ext => file.name.toLowerCase().endsWith(ext));
    const hasValidMime = validMimes.includes((file.type || '').toLowerCase());
    if (!hasValidExt && !hasValidMime) {
      alert('Unsupported file format. Please upload an image creative in PNG, JPG, or WEBP format.');
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    setUploadingPoster(true);
    try {
      const uploadRes = await api.uploadPoster(file);
      setPosterFilePath(uploadRes.file_path);
      setPosterAssetId(null);
      setIsPdf(false);
      setPdfPageCount(1);
      setPdfPages([]);
      setSelectedPage(1);
      setPageFilter('all');
      setPosterMeta({
        filename: uploadRes.filename,
        width: uploadRes.width,
        height: uploadRes.height,
        color_mode: uploadRes.color_mode,
        format: uploadRes.format
      });
      setPosterPreviewUrl(URL.createObjectURL(file));
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
    if (!trimmedTitle) {
      alert('Please provide a title before saving or running checks.');
      return null;
    }
    const brandIdToUse = selectedBrandId || (brands.length > 0 ? brands[0].id : '');
    if (!brandIdToUse && !selectedContent) {
      alert('Please select a brand.');
      return null;
    }

    const trimmedBody = bodyText.trim();
    const hasPoster = Boolean(posterFilePath);

    if (contentType === 'image') {
      if (!hasPoster) {
        alert('Please upload an advertisement image for an Image Advertisement.');
        return null;
      }
    } else if (contentType === 'text') {
      if (!trimmedBody) {
        alert('Please provide marketing copy text for a Text Advertisement.');
        return null;
      }
    } else {
      // 'both'
      if (!trimmedBody && !hasPoster) {
        alert('Please provide marketing copy and upload an advertisement image for an Image + Text Advertisement.');
        return null;
      }
      if (!trimmedBody) {
        alert('Please provide marketing copy text for an Image + Text Advertisement.');
        return null;
      }
      if (!hasPoster) {
        alert('Please upload an advertisement image for an Image + Text Advertisement.');
        return null;
      }
    }

    const bodyToSave = contentType === 'image' ? '' : trimmedBody;
    const posterPathToSave = contentType === 'text' ? undefined : (posterFilePath || undefined);
    const posterAssetIdToSave = contentType === 'text' ? undefined : (posterAssetId || undefined);
    const posterAltToSave = contentType === 'text' ? undefined : (posterAltText ? posterAltText.trim() : undefined);
    const channelToSave = channel || 'General';

    setSaving(true);
    try {
      let savedItem: ContentItem;
      if (selectedContent) {
        savedItem = await api.updateContentItem(
          selectedContent.id,
          bodyToSave,
          trimmedTitle,
          channelToSave,
          posterPathToSave,
          posterAssetIdToSave,
          posterAltToSave,
          selectedProductId || undefined
        );
      } else {
        savedItem = await api.createContentItem(
          brandIdToUse,
          trimmedTitle,
          channelToSave,
          bodyToSave,
          posterPathToSave,
          posterAssetIdToSave,
          posterAltToSave,
          selectedProductId || undefined
        );
      }

      // Synchronize editor state with the exact persisted version
      setSelectedContent(savedItem);
      setTitle(savedItem.title);
      setChannel(savedItem.channel || 'General');
      setSelectedBrandId(savedItem.brand_id);
      setSelectedProductId(savedItem.product_id || '');
      if (contentType !== 'image') {
        setBodyText(savedItem.latest_version?.body_text || '');
      }

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
      } catch (e) {
        console.warn('Failed to refresh versions:', e);
      }

      setIsDirty(false);
      setGovError(null);
      await loadContents(true);
      return savedItem;
    } catch (err: any) {
      alert(`Save draft error: ${err.message}`);
      return null;
    } finally {
      setSaving(false);
    }
  };

  const handleSaveDraft = async () => {
    const saved = await saveDraftInternal();
    if (saved) {
      alert(`Draft revision v${saved.current_version_num} saved successfully!`);
    }
  };

  const handleRunChecks = async () => {
    let itemToEvaluate = selectedContent;
    if (isDirty || !selectedContent) {
      const saved = await saveDraftInternal();
      if (!saved) return;
      itemToEvaluate = saved;
    }

    if (!itemToEvaluate || !itemToEvaluate.latest_version) {
      alert('Please save the draft content first.');
      return;
    }

    const versionId = itemToEvaluate.latest_version.id;
    const versionNum = itemToEvaluate.latest_version.version_num;
    setChecking(true);
    setGovError(null);
    try {
      const run = await api.runGovernanceCheck(versionId, selectedProductId || undefined);
      setLatestGovRun(run);
      setCheckedVersionId(versionId);
      setCheckedVersionNum(versionNum);
      const sugMap: Record<string, CorrectionSuggestion> = {};
      if (run.findings) {
        run.findings.forEach(f => {
          if (f.suggestion) sugMap[f.id] = f.suggestion;
        });
      }
      setSuggestions(sugMap);
    } catch (err: any) {
      setGovError(err.message || 'Governance check failed.');
    } finally {
      setChecking(false);
    }
  };

  // Suggestion Action Handlers
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

  // Filter drafts for drawer
  const filteredDrafts = useMemo(() => {
    if (!draftSearchQuery.trim()) return contentList;
    const q = draftSearchQuery.toLowerCase();
    return contentList.filter(c => {
      const brand = brands.find(b => b.id === c.brand_id);
      return (
        c.title.toLowerCase().includes(q) ||
        (brand && brand.name.toLowerCase().includes(q)) ||
        c.channel.toLowerCase().includes(q) ||
        c.status.toLowerCase().includes(q)
      );
    });
  }, [contentList, draftSearchQuery, brands]);

  return (
    <div>
      {/* Scoped CSS for Two-Column Responsive Layout */}
      <style>{`
        .content-studio-layout {
          display: grid;
          grid-template-columns: minmax(0, 1.62fr) minmax(0, 1fr);
          gap: 24px;
          align-items: start;
        }
        @media (max-width: 1040px) {
          .content-studio-layout {
            grid-template-columns: 1fr;
          }
        }
        .config-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 14px;
        }
        @media (max-width: 768px) {
          .config-grid {
            grid-template-columns: 1fr;
          }
        }
        .content-type-selector {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 10px;
        }
        @media (max-width: 640px) {
          .content-type-selector {
            grid-template-columns: 1fr;
          }
        }
        .action-bar-container {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding-top: 16px;
          border-top: 1px solid var(--border-subtle);
          margin-top: 8px;
          flex-wrap: wrap;
          gap: 12px;
        }
      `}</style>

      {/* Top Header */}
      <div className="flex-between" style={{ marginBottom: 20, flexWrap: 'wrap', gap: 14 }}>
        <div>
          <h1 className="title-xl">Content Studio & Unified Governance</h1>
          <p className="text-sub">
            Author marketing copy, attach poster creatives, evaluate unified text and visual brand rules, and lock immutable versions for approval.
          </p>
        </div>

        {/* Existing New Draft Action remains at top-right */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button
            type="button"
            onClick={() => setDraftsDrawerOpen(true)}
            className="btn btn-secondary"
            style={{ fontSize: '0.82rem', padding: '7px 14px', display: 'inline-flex', alignItems: 'center', gap: 6 }}
            title="Open drafts and revision history drawer"
          >
            <FolderOpen size={15} color="#4ade80" />
            Drafts ({contentList.length})
          </button>
          <button
            id="new-draft-btn"
            onClick={handleCreateNewDraft}
            className="btn btn-primary"
            style={{ fontSize: '0.82rem', padding: '7px 14px', display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <Plus size={16} /> New Draft
          </button>
        </div>
      </div>

      {/* 1. CLEAN TWO-COLUMN LAYOUT: Content Editor (62%) + Unified Governance (38%) */}
      <div className="content-studio-layout">
        {/* =================================================================== */}
        {/* LEFT COLUMN: CONTENT EDITOR (60–65% width) */}
        {/* =================================================================== */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 20, padding: 24 }}>
          {/* A. DRAFT HEADER */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {/* Top row: Draft Switcher + Status indicators */}
            <div className="flex-between" style={{ flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
              {/* Compact Draft Switcher Dropdown */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 260 }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                  Current Draft:
                </span>
                <select
                  value={selectedContent?.id || ''}
                  onChange={(e) => {
                    if (e.target.value === '__new__') {
                      handleCreateNewDraft();
                    } else {
                      const found = contentList.find(c => c.id === e.target.value);
                      if (found) selectDraft(found);
                    }
                  }}
                  className="select"
                  style={{
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    padding: '6px 12px',
                    height: 38,
                    background: '#111613',
                    flex: 1,
                    maxWidth: 360
                  }}
                >
                  {contentList.length === 0 ? (
                    <option value="">(No existing drafts)</option>
                  ) : (
                    contentList.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.title} (v{item.current_version_num})
                      </option>
                    ))
                  )}
                  <option value="__new__">+ Create New Draft...</option>
                </select>
              </div>

              {/* Compact Draft Status Indicators */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {selectedContent && (
                  <>
                    <span style={{
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      padding: '3px 8px',
                      borderRadius: 4,
                      background: 'rgba(255, 255, 255, 0.06)',
                      color: '#cbd5e1'
                    }}>
                      v{selectedContent.current_version_num}
                    </span>
                    <StatusBadge status={selectedContent.status} />
                  </>
                )}
                {isDirty && (
                  <span style={{
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    padding: '3px 8px',
                    borderRadius: 4,
                    background: 'rgba(245, 158, 11, 0.15)',
                    color: '#fbbf24',
                    border: '1px solid rgba(245, 158, 11, 0.3)'
                  }}>
                    Unsaved Edits
                  </span>
                )}
              </div>
            </div>

            {/* Draft Title Input */}
            <div>
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
                style={{
                  fontSize: '1.05rem',
                  fontWeight: 600,
                  height: 44,
                  padding: '10px 14px',
                  background: '#111613'
                }}
              />
            </div>
          </div>

          {/* B. CONTENT TYPE & CONFIGURATION */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Content Type Selector */}
            <div>
              <label className="form-label" style={{ marginBottom: 6, display: 'block' }}>Content Type</label>
              <div className="content-type-selector">
                <button
                  type="button"
                  data-testid="content-type-image"
                  onClick={() => { setContentType('image'); setIsDirty(true); }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: contentType === 'image' ? '1.5px solid #22c55e' : '1px solid var(--border-subtle)',
                    background: contentType === 'image' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                    color: contentType === 'image' ? '#4ade80' : 'var(--text-muted)',
                    fontWeight: contentType === 'image' ? 600 : 500,
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <ImageIcon size={16} color={contentType === 'image' ? '#22c55e' : 'currentColor'} />
                  Image Advertisement
                </button>
                <button
                  type="button"
                  data-testid="content-type-text"
                  onClick={() => { setContentType('text'); setIsDirty(true); }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: contentType === 'text' ? '1.5px solid #22c55e' : '1px solid var(--border-subtle)',
                    background: contentType === 'text' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                    color: contentType === 'text' ? '#4ade80' : 'var(--text-muted)',
                    fontWeight: contentType === 'text' ? 600 : 500,
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <FileText size={16} color={contentType === 'text' ? '#22c55e' : 'currentColor'} />
                  Text Advertisement
                </button>
                <button
                  type="button"
                  data-testid="content-type-both"
                  onClick={() => { setContentType('both'); setIsDirty(true); }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: contentType === 'both' ? '1.5px solid #22c55e' : '1px solid var(--border-subtle)',
                    background: contentType === 'both' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                    color: contentType === 'both' ? '#4ade80' : 'var(--text-muted)',
                    fontWeight: contentType === 'both' ? 600 : 500,
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <Layers size={16} color={contentType === 'both' ? '#22c55e' : 'currentColor'} />
                  Image + Text Advertisement
                </button>
              </div>
            </div>

            {/* Brand and Target Product Grid (2 columns) */}
            <div className="config-grid">
              {/* Brand */}
              <div>
                <label className="form-label" style={{ marginBottom: 6, display: 'block' }}>Brand</label>
                <select
                  value={selectedBrandId}
                  onChange={(e) => {
                    setSelectedBrandId(e.target.value);
                    setIsDirty(true);
                  }}
                  className="select"
                  style={{ height: 40, fontSize: '0.82rem', padding: '6px 10px', background: '#111613' }}
                >
                  {brands.length === 0 ? (
                    <option value="">Default Brand</option>
                  ) : (
                    brands.map((b) => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))
                  )}
                </select>
              </div>

              {/* Target Product (Catalogue) */}
              <div>
                <label className="form-label" style={{ marginBottom: 6, display: 'block' }}>Target Product</label>
                <select
                  value={selectedProductId}
                  onChange={(e) => {
                    setSelectedProductId(e.target.value);
                    setIsDirty(true);
                  }}
                  className="select"
                  style={{ height: 40, fontSize: '0.82rem', padding: '6px 10px', background: '#111613' }}
                >
                  <option value="">General / All Catalogue Products</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.product_name} {p.sku ? `(${p.sku})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* C & D. MARKETING COPY EDITOR (Visible for Text and Image + Text) */}
          {(contentType === 'text' || contentType === 'both') && (
            <>
          {/* C. MARKETING COPY EDITOR */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div className="flex-between">
              <label className="form-label" style={{ marginBottom: 0 }}>Marketing Copy Text</label>
              <span style={{ fontSize: '0.74rem', color: 'var(--text-dim)' }}>
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
              style={{
                minHeight: 180,
                fontSize: '0.92rem',
                lineHeight: 1.6,
                padding: '12px 14px',
                background: '#111613'
              }}
            />
          </div>

          {/* D. REAL-TIME IN-EDITOR ASSISTANT (Compact Status Row + Expandable Infractions) */}
          <div style={{
            padding: '12px 14px',
            borderRadius: 8,
            background: liveInfractions.length > 0
              ? 'rgba(239, 68, 68, 0.05)'
              : (bodyText.trim() ? 'rgba(34, 197, 94, 0.04)' : 'rgba(255, 255, 255, 0.02)'),
            border: `1px solid ${liveInfractions.length > 0 ? 'rgba(239, 68, 68, 0.22)' : (bodyText.trim() ? 'rgba(34, 197, 94, 0.2)' : 'rgba(255, 255, 255, 0.06)')}`
          }}>
            {/* Compact Informational Status Row */}
            <div className="flex-between" style={{ alignItems: 'center', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: isLiveChecking ? '#38bdf8' : (liveInfractions.length > 0 ? '#ef4444' : (bodyText.trim() ? '#22c55e' : '#64748b')),
                  boxShadow: isLiveChecking ? '0 0 8px #38bdf8' : 'none',
                  flexShrink: 0
                }} />
                <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#e2e8f0', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Sparkles size={14} color="#4ade80" />
                  In-Editor Real-Time Assistant
                  <span style={{ fontSize: '0.68rem', color: 'var(--text-dim)', fontWeight: 400 }}>
                    (Preliminary Copy Checks • 600ms Debounce)
                  </span>
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: 999,
                  background: liveInfractions.length > 0 ? 'rgba(239, 68, 68, 0.18)' : (bodyText.trim() ? 'rgba(34, 197, 94, 0.12)' : 'rgba(255, 255, 255, 0.05)'),
                  color: liveInfractions.length > 0 ? '#f87171' : (bodyText.trim() ? '#4ade80' : 'var(--text-dim)')
                }}>
                  {isLiveChecking ? 'Analyzing...' : (!bodyText.trim() ? 'Awaiting copy' : (liveInfractions.length === 0 ? '✓ Copy is Clean' : `${liveInfractions.length} Issue${liveInfractions.length > 1 ? 's' : ''} Detected`))}
                </span>

                {liveInfractions.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setIsRealTimeExpanded(!isRealTimeExpanded)}
                    style={{
                      background: 'transparent',
                      border: '1px solid rgba(255,255,255,0.12)',
                      borderRadius: 4,
                      color: 'var(--text-muted)',
                      fontSize: '0.7rem',
                      padding: '2px 8px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4
                    }}
                  >
                    {isRealTimeExpanded ? 'Hide Details ▲' : 'Show Details ▼'}
                  </button>
                )}
              </div>
            </div>

            {/* Concise Summary when collapsed */}
            {liveInfractions.length > 0 && !isRealTimeExpanded && (
              <div style={{
                marginTop: 8,
                padding: '6px 10px',
                borderRadius: 6,
                background: 'rgba(0,0,0,0.2)',
                fontSize: '0.73rem',
                color: 'var(--text-muted)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 8
              }}>
                <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  <span style={{ color: '#fca5a5', fontWeight: 600 }}>Summary:</span> {liveInfractions.map(i => i.title).join(' • ')}
                </div>
                <button
                  type="button"
                  onClick={() => setIsRealTimeExpanded(true)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#4ade80',
                    cursor: 'pointer',
                    fontSize: '0.7rem',
                    textDecoration: 'underline',
                    whiteSpace: 'nowrap',
                    padding: 0
                  }}
                >
                  Review & Fix
                </button>
              </div>
            )}

            {/* Contained Expandable In-Editor Live Infractions List */}
            {liveInfractions.length > 0 && isRealTimeExpanded && (
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                marginTop: 10,
                maxHeight: 220,
                overflowY: 'auto',
                paddingRight: 4
              }}>
                {liveInfractions.map((inf) => (
                  <div key={inf.id} style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 10px',
                    borderRadius: 6,
                    background: 'rgba(0,0,0,0.25)',
                    border: '1px solid rgba(255,255,255,0.06)',
                    gap: 8
                  }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginRight: 8, flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '0.78rem', fontWeight: 600, color: inf.severity === 'error' ? '#f87171' : '#fbbf24', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <AlertTriangle size={13} style={{ flexShrink: 0 }} />
                        <span>{inf.title}</span>
                        {inf.rule_code && <span style={{ fontSize: '0.68rem', opacity: 0.7, fontFamily: 'monospace' }}>[{inf.rule_code}]</span>}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', lineHeight: 1.35 }}>
                        {inf.explanation}
                      </div>
                    </div>
                    {inf.can_autofix && inf.replacement_text && (
                      <button
                        type="button"
                        onClick={() => applyLiveAutoFix(inf)}
                        className="btn btn-primary"
                        style={{
                          padding: '4px 10px',
                          fontSize: '0.72rem',
                          background: '#22c55e', color: '#052e16', fontWeight: 600,
                          whiteSpace: 'nowrap',
                          gap: 4,
                          flexShrink: 0
                        }}
                      >
                        <Sparkles size={12} /> Auto-Fix
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

            </>
          )}

          {/* E. ADVERTISEMENT CREATIVE POSTER (Visible for Image and Image + Text) */}
          {(contentType === 'image' || contentType === 'both') && (
          <div style={{
            padding: 16,
            borderRadius: 10,
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            gap: 12
          }}>
            <div className="flex-between">
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#93c5fd', display: 'flex', alignItems: 'center', gap: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
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
                {/* Clean Dropzone Upload Area */}
                <div
                  style={{
                    border: '2px dashed rgba(255,255,255,0.14)',
                    borderRadius: 8,
                    padding: '24px 16px',
                    textAlign: 'center',
                    background: 'rgba(0,0,0,0.2)',
                    cursor: 'pointer',
                    transition: 'border 0.2s'
                  }}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload size={26} color="#4ade80" style={{ margin: '0 auto 8px auto' }} />
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#e2e8f0' }}>
                    {uploadingPoster ? 'Uploading creative...' : 'Upload Advertisement Creative Artwork'}
                  </div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--text-dim)', marginTop: 4 }}>
                    Supports PNG, JPG, or WEBP up to 15MB (max 4096 px).
                  </div>
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileUpload}
                    accept="image/png,image/jpeg,image/webp"
                    style={{ display: 'none' }}
                  />
                </div>

                {/* User-Facing Poster Size Recommendation & Infrastructure Notice */}
                <div style={{
                  padding: '12px 14px',
                  borderRadius: 8,
                  background: 'linear-gradient(180deg, #18221b 0%, #111613 100%)', border: '1px solid rgba(74, 222, 128, 0.2)',
                  fontSize: '0.76rem',
                  lineHeight: 1.5,
                  textAlign: 'left',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6
                }}>
                  <div style={{ fontWeight: 600, color: '#4ade80', display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.80rem' }}>
                    <Info size={15} color="#4ade80" style={{ flexShrink: 0 }} />
                    Recommended Poster Size: 835 × 1080 px
                  </div>
                  <div style={{ color: '#cbd5e1' }}>
                    For the best balance of image clarity and reliable processing, we recommend uploading posters at 835 × 1080 pixels.
                  </div>
                  <div style={{ color: '#94a3b8', fontSize: '0.73rem' }}>
                    Other dimensions are accepted, but larger images will be proportionally resized before analysis.
                  </div>
                  <div style={{
                    fontSize: '0.71rem',
                    color: '#94a3b8',
                    borderTop: '1px solid rgba(255,255,255,0.06)',
                    paddingTop: 6,
                    marginTop: 2
                  }}>
                    Why this size limit? Inkloom AI currently operates on Render&apos;s free-tier hosting, which has limited memory resources. We use optimized image dimensions to reduce memory consumption and help maintain reliable poster analysis. This restriction is intended to keep the service stable without requiring paid infrastructure.
                  </div>
                </div>

                {assets.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: '0.74rem', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
                      Or attach approved brand asset:
                    </span>
                    <select
                      className="select"
                      style={{ fontSize: '0.78rem', padding: '6px 10px', height: 36, background: '#111613' }}
                      onChange={(e) => e.target.value && handleSelectBrandAsset(e.target.value)}
                      defaultValue=""
                    >
                      <option value="" disabled>Choose from Brand Assets...</option>
                      {assets.map(a => (
                        <option key={a.id} value={a.id}>
                          {a.asset_name} ({a.asset_type.replace(/_/g, ' ')})
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {/* PDF Page Navigation Selector */}
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
                            border: isCur ? '1px solid #22c55e' : '1px solid rgba(255,255,255,0.1)',
                            background: isCur ? 'rgba(34, 197, 94, 0.25)' : 'rgba(255,255,255,0.04)',
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

                {/* Oversized Poster Informational Warning */}
                {!isPdf && posterMeta?.width && posterMeta?.height && (posterMeta.width > 835 || posterMeta.height > 1080) && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    padding: '10px 14px',
                    borderRadius: 8,
                    background: 'rgba(74, 222, 128, 0.08)', border: '1px solid rgba(74, 222, 128, 0.25)',
                    color: '#cbd5e1',
                    fontSize: '0.78rem',
                    lineHeight: 1.5
                  }}>
                    <Info size={16} color="#4ade80" style={{ flexShrink: 0, marginTop: 2 }} />
                    <div>
                      <div style={{ fontWeight: 600, color: '#e0e7ff', marginBottom: 2 }}>
                        Image Resized for Analysis
                      </div>
                      <div>
                        Your image exceeds the recommended processing dimensions of 835 × 1080 px. Inkloom AI will automatically resize it proportionally before analysis. Your original image will remain unchanged.
                      </div>
                    </div>
                  </div>
                )}

                {/* Poster Preview and Info Row */}
                <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                  {posterPreviewUrl ? (
                    <div style={{ position: 'relative', flexShrink: 0 }}>
                      <img
                        src={posterPreviewUrl}
                        alt={posterAltText || (isPdf ? `Page ${selectedPage} preview` : 'Poster preview')}
                        style={{
                          width: 120,
                          height: 120,
                          objectFit: 'contain',
                          borderRadius: 8,
                          background: '#111613',
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
                          background: 'rgba(0,0,0,0.8)',
                          color: '#fff',
                          fontSize: '0.62rem',
                          padding: '1px 5px',
                          borderRadius: 3,
                          fontWeight: 700
                        }}>
                          p. {selectedPage}/{pdfPageCount}
                        </span>
                      )}
                    </div>
                  ) : (
                    <div style={{
                      width: 120,
                      height: 120,
                      borderRadius: 8,
                      background: 'rgba(99, 102, 241, 0.1)',
                      border: '1px solid rgba(99, 102, 241, 0.3)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}>
                      <ImageIcon size={36} color="#4ade80" />
                    </div>
                  )}

                  <div style={{ flex: 1, fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.88rem' }}>
                      {posterMeta?.filename || (isPdf ? `PDF Creative Deck (${pdfPageCount} Pages)` : 'Creative Asset Attached')}
                    </div>
                    {isPdf && pdfPages[selectedPage - 1] && (
                      <div>
                        Page {selectedPage}: <strong>{pdfPages[selectedPage - 1].width_px}x{pdfPages[selectedPage - 1].height_px}px</strong> ({pdfPages[selectedPage - 1].orientation})
                      </div>
                    )}
                    {!isPdf && posterMeta?.width && posterMeta?.height && (
                      <div>
                        Original Resolution: <strong>{posterMeta.width}x{posterMeta.height}px</strong> ({posterMeta.color_mode || 'RGB'})
                        {(posterMeta.width > 835 || posterMeta.height > 1080) && (
                          <span style={{ marginLeft: 6, color: '#4ade80', fontSize: '0.72rem' }}>
                            (governance analyzed within 835×1080 bounds)
                          </span>
                        )}
                      </div>
                    )}
                    <div style={{ fontSize: '0.74rem', color: '#34d399', marginTop: 2 }}>
                      ✓ {isPdf ? `Page-level visual, logo and text governance evaluated across all ${pdfPageCount} pages` : 'Visual governance checks will run automatically with text checks'}
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
                    placeholder={isPdf ? "Describe the overall presentation deck content..." : "Describe the image content and visual text for screen-reader accessibility..."}
                    style={{ fontSize: '0.82rem', padding: '8px 12px', background: '#111613' }}
                  />
                </div>
              </div>
            )}
          </div>

          )}

          {/* 4. ACTION BUTTONS (Positioned consistently at bottom of Content Editor) */}
          <div className="action-bar-container">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {selectedContent && (
                <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                  Current Version: <strong>v{selectedContent.current_version_num}</strong>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <button
                id="save-draft-btn"
                onClick={handleSaveDraft}
                disabled={saving || checking}
                className="btn btn-secondary"
                style={{ fontSize: '0.85rem', padding: '8px 16px' }}
              >
                {saving ? 'Saving...' : 'Save Draft Revision'}
              </button>

              <button
                id="run-governance-btn"
                onClick={handleRunChecks}
                disabled={saving || checking}
                className="btn btn-primary"
                style={{
                  fontSize: '0.85rem',
                  padding: '8px 18px',
                  background: 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)', color: '#052e16', fontWeight: 700, boxShadow: '0 4px 14px rgba(34, 197, 94, 0.3)'
                }}
              >
                <Play size={15} /> {checking ? 'Evaluating...' : 'Run Governance Check'}
              </button>

              {selectedContent && isCreator && selectedContent.status !== 'approved' && (
                <button
                  id="submit-approval-btn"
                  onClick={() => setSubmitModalOpen(true)}
                  disabled={saving || checking || submitting}
                  className="btn btn-success"
                  style={{ fontSize: '0.85rem', padding: '8px 16px' }}
                >
                  <Send size={15} /> Submit for Approval
                </button>
              )}
            </div>
          </div>
        </div>

        {/* =================================================================== */}
        {/* RIGHT COLUMN: UNIFIED GOVERNANCE PANEL (35–40% width) */}
        {/* =================================================================== */}
        <div className="card" style={{
          display: 'flex',
          flexDirection: 'column',
          padding: 24,
          gap: 16,
          boxSizing: 'border-box',
          overflow: 'visible'
        }}>
          <GovernanceReviewPanel
            latestGovRun={latestGovRun}
            checkedVersionNum={checkedVersionNum}
            checkedVersionId={checkedVersionId}
            isDirty={isDirty}
            isPdf={isPdf}
            pdfPageCount={pdfPageCount}
            selectedPage={selectedPage}
            onSelectPage={setSelectedPage}
            govError={govError}
            checking={checking}
            onRunChecks={handleRunChecks}
            suggestions={suggestions}
            suggestionApplying={suggestionApplying}
            onAcceptSuggestion={handleAcceptSuggestion}
            onRejectSuggestion={handleRejectSuggestion}
            onOpenCustomEdit={handleOpenCustomEdit}
            suggestionBanner={suggestionBanner}
            onCloseSuggestionBanner={() => setSuggestionBanner(null)}
          />
        </div>
      </div>

      {/* =================================================================== */}
      {/* COLLAPSIBLE DRAFTS & REVISION HISTORY DRAWER */}
      {/* =================================================================== */}
      {draftsDrawerOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          justifyContent: 'flex-start',
          zIndex: 100
        }}>
          <div className="card" style={{
            width: 420,
            maxWidth: '90vw',
            height: '100vh',
            borderRadius: 0,
            borderRight: '1px solid var(--border-subtle)',
            background: '#0c100e',
            display: 'flex',
            flexDirection: 'column',
            padding: 20
          }}>
            {/* Drawer Header */}
            <div className="flex-between" style={{ marginBottom: 16, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <FolderOpen size={18} color="#4ade80" />
                  Drafts & Revision History
                </h3>
                <span style={{ fontSize: '0.74rem', color: 'var(--text-dim)' }}>
                  {contentList.length} total drafts in organization
                </span>
              </div>
              <button
                type="button"
                onClick={() => setDraftsDrawerOpen(false)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Search Filter inside Drawer */}
            <div style={{ position: 'relative', marginBottom: 14 }}>
              <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
              <input
                type="text"
                placeholder="Search drafts by title, brand..."
                value={draftSearchQuery}
                onChange={(e) => setDraftSearchQuery(e.target.value)}
                className="input"
                style={{ paddingLeft: 32, fontSize: '0.82rem', height: 36, background: '#111613' }}
              />
            </div>

            {/* Drafts List */}
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8, paddingRight: 4 }}>
              {filteredDrafts.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-dim)', fontSize: '0.82rem' }}>
                  No drafts found matching search.
                </div>
              ) : (
                filteredDrafts.map((item) => {
                  const isSelected = selectedContent?.id === item.id;
                  const hasPoster = Boolean(item.latest_version?.poster_file_path);
                  const itemBrand = brands.find(b => b.id === item.brand_id);

                  return (
                    <div
                      key={item.id}
                      onClick={() => {
                        selectDraft(item);
                        setDraftsDrawerOpen(false);
                      }}
                      style={{
                        padding: 12,
                        borderRadius: 8,
                        background: isSelected ? 'rgba(34, 197, 94, 0.15)' : 'rgba(255, 255, 255, 0.02)', border: isSelected ? '1px solid rgba(34, 197, 94, 0.4)' : '1px solid var(--border-subtle)',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div style={{ fontWeight: 600, fontSize: '0.88rem', color: isSelected ? '#fff' : 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 220 }}>
                          {item.title}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          {hasPoster && (
                            <span title="Poster attached" style={{ color: '#38bdf8' }}>
                              <ImageIcon size={13} />
                            </span>
                          )}
                          <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: 4, background: 'rgba(255,255,255,0.08)', color: '#cbd5e1' }}>
                            v{item.current_version_num}
                          </span>
                        </div>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                        <StatusBadge status={item.status} />
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>{itemBrand?.name || 'General Draft'}</span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Version History Sub-Panel for Selected Draft */}
            {selectedContent && versions.length > 0 && (
              <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#a5b4fc', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <History size={14} /> Immutable Version History (Selected Draft)
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 160, overflowY: 'auto' }}>
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
                        sha256: {ver.checksum.slice(0, 20)}...
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Bottom New Draft Button */}
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border-subtle)' }}>
              <button
                type="button"
                onClick={() => {
                  handleCreateNewDraft();
                  setDraftsDrawerOpen(false);
                }}
                className="btn btn-primary"
                style={{ width: '100%', fontSize: '0.82rem', padding: '8px 12px' }}
              >
                <Plus size={15} /> Create Brand New Draft
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* SUBMIT FOR APPROVAL MODAL */}
      {/* =================================================================== */}
      {submitModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100,
          padding: 20
        }}>
          <div className="card" style={{ width: 480, background: '#131b2e', border: '1px solid rgba(255,255,255,0.15)' }}>
            <h2 className="title-md" style={{ marginBottom: 12 }}>
              Submit for Human Approval
            </h2>
            <p className="text-sub" style={{ marginBottom: 14, fontSize: '0.82rem' }}>
              This will lock <strong>Version {selectedContent?.current_version_num}</strong> with immutable checksum:
              <br />
              <code style={{ fontSize: '0.72rem', color: '#a5b4fc', display: 'block', marginTop: 4 }}>
                {selectedContent?.latest_version?.checksum.slice(0, 24)}...
              </code>
              {selectedContent?.latest_version?.poster_file_path && (
                <span style={{ display: 'block', fontSize: '0.75rem', color: '#38bdf8', marginTop: 6 }}>
                  ✓ Includes attached creative poster in locked version bundle
                </span>
              )}
            </p>

            <div className="form-group" style={{ marginBottom: 16 }}>
              <label className="form-label">Submission Notes for Approval Manager</label>
              <textarea
                value={submitNotes}
                onChange={(e) => setSubmitNotes(e.target.value)}
                className="textarea"
                placeholder="e.g., Reviewed against Q4 guidelines. All medical claims removed, poster contrast and brand colors verified."
                style={{ minHeight: 80, fontSize: '0.82rem', background: '#111613' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
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

      {/* =================================================================== */}
      {/* CUSTOM EDIT SUGGESTION MODAL */}
      {/* =================================================================== */}
      {customEditModalOpen && activeSuggestionForEdit && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 110,
          padding: 20
        }}>
          <div className="card" style={{ width: 520, background: '#131b2e', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Sparkles size={16} color="#4ade80" />
              Customize Correction Before Applying
            </h3>
            <p className="text-sub" style={{ marginBottom: 12, fontSize: '0.8rem' }}>
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
                style={{ width: '100%', fontFamily: 'inherit', fontSize: '0.82rem', background: '#111613' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
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
