import React, { useEffect, useState } from 'react';
import {
  Upload,
  BookOpen,
  CheckCircle,
  XCircle,
  FileText,
  AlertCircle,
  Filter,
  Check,
  X,
  FileCheck,
  Shield,
  Tag,
  Edit3,
  RefreshCw,
  Quote,
  AlertTriangle,
  Download,
  ExternalLink,
  Image as ImageIcon,
  Info,
  ChevronDown,
  ChevronUp,
  Sparkles,
  HelpCircle,
  FileCheck2,
  ArrowRight,
  ShieldCheck,
  Plus
} from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { StatusBadge } from '../components/StatusBadge';
import { KnowledgeRule, KnowledgeFact, KnowledgeSource, BrandAsset, Brand } from '../types';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

export const KnowledgeLibrary: React.FC = () => {
  const { role } = useAuth();
  const [searchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const initialTab = (tabParam && ['rules', 'facts', 'assets', 'sources'].includes(tabParam))
    ? (tabParam as 'rules' | 'facts' | 'assets' | 'sources')
    : 'rules';

  const [activeTab, setActiveTab] = useState<'rules' | 'facts' | 'assets' | 'sources'>(initialTab);

  useEffect(() => {
    if (tabParam && ['rules', 'facts', 'assets', 'sources'].includes(tabParam)) {
      setActiveTab(tabParam as 'rules' | 'facts' | 'assets' | 'sources');
    }
  }, [tabParam]);

  const [rules, setRules] = useState<KnowledgeRule[]>([]);
  const [facts, setFacts] = useState<KnowledgeFact[]>([]);
  const [assets, setAssets] = useState<BrandAsset[]>([]);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);

  // Onboarding & Upload modal state
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadModalTab, setUploadModalTab] = useState<'required' | 'optional' | 'single'>('required');
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadStepMsg, setUploadStepMsg] = useState<string | null>(null);
  const [uploadMsg, setUploadMsg] = useState<{ type: 'success' | 'error'; text: string; details?: string[] } | null>(null);

  // Required inputs state
  const [guidelinesFile, setGuidelinesFile] = useState<File | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null);

  // Optional inputs state
  const [optionalFile, setOptionalFile] = useState<File | null>(null);
  const [optionalType, setOptionalType] = useState('pdf_product_knowledge');

  // Single file fallback state (for backward compatibility)
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadType, setUploadType] = useState('pdf_brand_guidelines');

  // Onboarding guidance toggle (defaults to true if sources are empty or can be toggled by user)
  const [showOnboardingGuide, setShowOnboardingGuide] = useState(true);

  // Filter state
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Rule edit modal state
  const [editRuleModalOpen, setEditRuleModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<KnowledgeRule | null>(null);
  const [editRuleForm, setEditRuleForm] = useState({
    title: '',
    pattern: '',
    explanation: '',
    severity: 'warning',
    rule_type: 'prohibited_word',
    review_notes: ''
  });
  const [savingEdit, setSavingEdit] = useState(false);

  // Fact edit modal state
  const [editFactModalOpen, setEditFactModalOpen] = useState(false);
  const [editingFact, setEditingFact] = useState<KnowledgeFact | null>(null);
  const [editFactForm, setEditFactForm] = useState({
    product_name: '',
    fact_key: '',
    fact_value: '',
    category: 'specification',
    review_notes: ''
  });

  // Reprocessing state
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);

  // Manual rule creation modal state
  const [addRuleModalOpen, setAddRuleModalOpen] = useState(false);
  const [newRuleForm, setNewRuleForm] = useState({
    title: '',
    pattern: '',
    explanation: '',
    severity: 'warning',
    rule_type: 'prohibited_word',
    source_id: '',
    page_number: '',
    evidence_passage: ''
  });
  const [savingNewRule, setSavingNewRule] = useState(false);

  // Document text viewing modal state
  const [viewTextModalOpen, setViewTextModalOpen] = useState(false);
  const [viewTextData, setViewTextData] = useState<any>(null);
  const [loadingText, setLoadingText] = useState(false);
  const [selectedTextPage, setSelectedTextPage] = useState<number>(1);

  const isReviewer = role === 'knowledge_reviewer' || role === 'org_admin';

  const loadData = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const [r, f, a, s, b] = await Promise.all([
        api.getRules(),
        api.getFacts(),
        api.getAssets(),
        api.getKnowledgeSources(),
        api.getBrands(),
      ]);
      setRules(r);
      setFacts(f);
      setAssets(a);
      setSources(s);
      setBrands(b);
      if (b.length > 0 && !selectedBrandId) {
        setSelectedBrandId(b[0].id);
      }
    } catch (err) {
      console.error('Failed to load knowledge data:', err);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    loadData(false);
  }, []);

  useAutoRefresh(() => {
    if (!uploading && !editRuleModalOpen && !editFactModalOpen && !reprocessingId) {
      loadData(true);
    }
  }, { intervalMs: 8000 });

  const categoryLabels: Record<string, string> = {
    pdf_brand_guidelines: 'PDF Brand Guidelines',
    pdf_product_knowledge: 'PDF Product Knowledge & Specs',
    supporting_doc: 'Supporting Evidence Document',
    brand_asset_image: 'Brand Asset / Creative Image',
  };

  const handleGuidelinesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    if (file) {
      if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
        alert("Invalid format: Brand guidelines must be uploaded as a PDF document.");
        e.target.value = '';
        setGuidelinesFile(null);
        return;
      }
      if (file.size > 25 * 1024 * 1024) {
        alert("File size exceeds 25 MB limit.");
        e.target.value = '';
        setGuidelinesFile(null);
        return;
      }
    }
    setGuidelinesFile(file);
  };

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    if (file) {
      const isAllowed = 
        file.type.startsWith('image/') || 
        file.name.toLowerCase().endsWith('.svg') ||
        file.name.toLowerCase().endsWith('.png') ||
        file.name.toLowerCase().endsWith('.jpg') ||
        file.name.toLowerCase().endsWith('.jpeg') ||
        file.name.toLowerCase().endsWith('.webp');
      if (!isAllowed) {
        alert("Invalid format: Logo must be an SVG, PNG, JPG/JPEG, or WebP image.");
        e.target.value = '';
        setLogoFile(null);
        setLogoPreviewUrl(null);
        return;
      }
      if (file.size > 25 * 1024 * 1024) {
        alert("Logo file size exceeds 25 MB limit.");
        e.target.value = '';
        setLogoFile(null);
        setLogoPreviewUrl(null);
        return;
      }
      setLogoFile(file);
      if (file.type.startsWith('image/') || file.name.endsWith('.svg')) {
        const url = URL.createObjectURL(file);
        setLogoPreviewUrl(url);
      } else {
        setLogoPreviewUrl(null);
      }
    } else {
      setLogoFile(null);
      setLogoPreviewUrl(null);
    }
  };

  const handleOpenAddRule = () => {
    setNewRuleForm({
      title: '',
      pattern: '',
      explanation: '',
      severity: 'warning',
      rule_type: 'prohibited_word',
      source_id: sources.length > 0 ? sources[0].id : '',
      page_number: '',
      evidence_passage: ''
    });
    setAddRuleModalOpen(true);
  };

  const handleSaveNewRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRuleForm.title.trim() || !newRuleForm.pattern.trim() || !newRuleForm.explanation.trim()) {
      alert("Please provide title, trigger pattern, and explanation for the rule.");
      return;
    }
    setSavingNewRule(true);
    try {
      const selectedSrc = sources.find(s => s.id === newRuleForm.source_id);
      await api.createRule({
        title: newRuleForm.title.trim(),
        pattern: newRuleForm.pattern.trim(),
        explanation: newRuleForm.explanation.trim(),
        severity: newRuleForm.severity,
        rule_type: newRuleForm.rule_type,
        source_id: newRuleForm.source_id || undefined,
        brand_id: selectedBrandId || (selectedSrc ? selectedSrc.brand_id : undefined) || (brands.length > 0 ? brands[0].id : undefined),
        source_citation: selectedSrc ? `${selectedSrc.filename}${newRuleForm.page_number ? `, Page ${newRuleForm.page_number}` : ''}` : undefined,
        page_number: newRuleForm.page_number ? parseInt(newRuleForm.page_number, 10) : undefined,
        evidence_passage: newRuleForm.evidence_passage.trim() || undefined,
        uncertainty_notes: "MANUAL_ENTRY: Created manually by reviewer. Human verification required before approval."
      });
      setAddRuleModalOpen(false);
      await loadData();
    } catch (err: any) {
      alert(`Failed to create rule: ${err.message || err}`);
    } finally {
      setSavingNewRule(false);
    }
  };

  const handleViewSourceText = async (sourceId: string, title: string) => {
    setLoadingText(true);
    setViewTextModalOpen(true);
    setViewTextData(null);
    setSelectedTextPage(1);
    try {
      const data = await api.getSourceText(sourceId);
      setViewTextData(data);
    } catch (err: any) {
      alert(`Could not fetch document text: ${err.message || err}`);
      setViewTextModalOpen(false);
    } finally {
      setLoadingText(false);
    }
  };

  const getExtractionMethodBadge = (rule: KnowledgeRule) => {
    if (rule.status === 'approved') {
      return (
        <span style={{ background: 'rgba(34, 197, 94, 0.15)', color: '#4ade80', border: '1px solid rgba(34, 197, 94, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>
          Approved Rule (Verified)
        </span>
      );
    }
    if (rule.uncertainty_notes && rule.uncertainty_notes.includes('LOCAL_EXTRACTION')) {
      return (
        <span style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>
          Local Text Extraction (Pending Review)
        </span>
      );
    }
    if (rule.uncertainty_notes && rule.uncertainty_notes.includes('MANUAL_ENTRY')) {
      return (
        <span style={{ background: 'rgba(236, 72, 153, 0.15)', color: '#f472b6', border: '1px solid rgba(236, 72, 153, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>
          Manual Entry (Pending Review)
        </span>
      );
    }
    return (
      <span style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', border: '1px solid rgba(245, 158, 11, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>
        AI Candidate (Pending Review)
      </span>
    );
  };

  const handleViewSamplePdf = (e: React.MouseEvent) => {
    e.preventDefault();
    const sampleUrl = '/samples/Willow_and_Vale_Brand_Governance_Manual_Sample.pdf';
    fetch(sampleUrl, { method: 'HEAD' })
      .then((res) => {
        const cType = res.headers.get('content-type') || '';
        if (res.ok && cType.includes('pdf')) {
          window.open(sampleUrl, '_blank', 'noopener,noreferrer');
        } else {
          alert(
            "Sample Document Staging Notice:\n\n" +
            "Expected location: frontend/public/samples/Willow_and_Vale_Brand_Governance_Manual_Sample.pdf\n\n" +
            "The sample reference PDF is not currently staged at this path in the public assets directory.\n" +
            "Once placed at this path, it will open directly in your browser as a downloadable reference manual."
          );
        }
      })
      .catch(() => {
        alert(
          "Sample Document Staging Notice:\n\n" +
          "Expected location: frontend/public/samples/Willow_and_Vale_Brand_Governance_Manual_Sample.pdf\n\n" +
          "The sample reference PDF is not currently staged at this path in the public assets directory.\n" +
          "Once placed at this path, it will open directly in your browser as a downloadable reference manual."
        );
      });
  };

  const handleRequiredOnboard = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!guidelinesFile && !logoFile) {
      alert("Please select at least one of the required items: Brand Guidelines (PDF) or Official Brand Logo.");
      return;
    }

    setUploading(true);
    setUploadMsg(null);
    setUploadStepMsg("Validating selected files...");

    const successItems: string[] = [];
    try {
      // 1. Upload Logo if provided
      if (logoFile) {
        setUploadStepMsg("1/2 Uploading official brand logo...");
        const logoData = new FormData();
        logoData.append('file', logoFile);
        logoData.append('title', 'Official Brand Logo');
        logoData.append('source_type', 'brand_asset_image');
        if (selectedBrandId) logoData.append('brand_id', selectedBrandId);

        await api.uploadKnowledge(logoData);
        successItems.push(`Official Brand Logo ('${logoFile.name}') uploaded as reference asset.`);
      }

      // 2. Upload Guidelines PDF if provided
      if (guidelinesFile) {
        setUploadStepMsg(logoFile ? "2/2 Uploading brand guidelines PDF & extracting candidate rules..." : "Uploading brand guidelines PDF & extracting candidate rules...");
        const guideData = new FormData();
        guideData.append('file', guidelinesFile);
        guideData.append('title', 'PDF Brand Guidelines');
        guideData.append('source_type', 'pdf_brand_guidelines');
        if (selectedBrandId) guideData.append('brand_id', selectedBrandId);

        const createdSource = await api.uploadKnowledge(guideData);
        successItems.push(`Brand Guidelines ('${guidelinesFile.name}') uploaded. Extracted ${createdSource.rules_count || 0} candidate rules and ${createdSource.facts_count || 0} facts into Pending Review.`);
      }

      setUploadMsg({
        type: 'success',
        text: 'Brand onboarding upload completed successfully!',
        details: successItems
      });

      setGuidelinesFile(null);
      setLogoFile(null);
      setLogoPreviewUrl(null);
      await loadData();
    } catch (err: any) {
      console.error("Onboarding upload error:", err);
      setUploadMsg({
        type: 'error',
        text: err.message || 'Brand onboarding upload failed. Please verify your connection and file format.',
        details: successItems.length > 0 ? [`Completed so far: ${successItems.join(', ')}`] : undefined
      });
    } finally {
      setUploading(false);
      setUploadStepMsg(null);
    }
  };

  const handleOptionalUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!optionalFile) {
      alert("Please select a file to upload.");
      return;
    }

    setUploading(true);
    setUploadMsg(null);
    setUploadStepMsg("Uploading optional knowledge resource...");

    try {
      const title = categoryLabels[optionalType] || 'Optional Knowledge Resource';
      const formData = new FormData();
      formData.append('file', optionalFile);
      formData.append('title', title);
      formData.append('source_type', optionalType);
      if (selectedBrandId) formData.append('brand_id', selectedBrandId);

      const created = await api.uploadKnowledge(formData);
      setUploadMsg({
        type: 'success',
        text: `Uploaded '${created.title}' (${created.filename}).`,
        details: optionalType.startsWith('pdf')
          ? [`Extracted ${created.rules_count || 0} candidate rules and ${created.facts_count || 0} facts into Pending Review.`]
          : [`Saved reference asset for image governance.`]
      });
      setOptionalFile(null);
      await loadData();
    } catch (err: any) {
      setUploadMsg({
        type: 'error',
        text: err.message || 'Upload failed.'
      });
    } finally {
      setUploading(false);
      setUploadStepMsg(null);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      alert('Please select a file to upload.');
      return;
    }

    setUploading(true);
    setUploadMsg(null);
    try {
      const generatedTitle = categoryLabels[uploadType] || 'Brand Knowledge Document';
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('title', generatedTitle);
      formData.append('source_type', uploadType);
      if (selectedBrandId) formData.append('brand_id', selectedBrandId);

      const createdSource = await api.uploadKnowledge(formData);
      setUploadMsg({
        type: 'success',
        text: `Uploaded '${createdSource.title}' (${createdSource.filename}). Extracted ${createdSource.rules_count || 0} candidate rules and ${createdSource.facts_count || 0} facts into Pending Review.`
      });
      setUploadFile(null);
      await loadData();
    } catch (err: any) {
      setUploadMsg({ type: 'error', text: err.message || 'Upload failed.' });
    } finally {
      setUploading(false);
    }
  };

  const handleReviewRule = async (ruleId: string, status: 'approved' | 'rejected') => {
    const notes = prompt(`Enter review notes for ${status.toUpperCase()}:`, `Reviewed by ${role}`);
    if (notes === null) return;
    try {
      await api.reviewRule(ruleId, status, notes);
      await loadData();
    } catch (err: any) {
      alert(`Review error: ${err.message}`);
    }
  };

  const handleOpenEditRule = (rule: KnowledgeRule) => {
    setEditingRule(rule);
    setEditRuleForm({
      title: rule.title,
      pattern: rule.pattern,
      explanation: rule.explanation,
      severity: rule.severity,
      rule_type: rule.rule_type,
      review_notes: rule.review_notes || ''
    });
    setEditRuleModalOpen(true);
  };

  const handleSaveRuleCorrection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingRule) return;
    setSavingEdit(true);
    try {
      await api.updateRule(editingRule.id, editRuleForm);
      setEditRuleModalOpen(false);
      setEditingRule(null);
      await loadData();
    } catch (err: any) {
      alert(`Correction error: ${err.message}`);
    } finally {
      setSavingEdit(false);
    }
  };

  const handleReviewFact = async (factId: string, status: 'approved' | 'rejected') => {
    const notes = prompt(`Enter review notes for ${status.toUpperCase()}:`, `Fact verified by ${role}`);
    if (notes === null) return;
    try {
      await api.reviewFact(factId, status, notes);
      await loadData();
    } catch (err: any) {
      alert(`Review error: ${err.message}`);
    }
  };

  const handleOpenEditFact = (fact: KnowledgeFact) => {
    setEditingFact(fact);
    setEditFactForm({
      product_name: fact.product_name,
      fact_key: fact.fact_key,
      fact_value: fact.fact_value,
      category: fact.category,
      review_notes: fact.review_notes || ''
    });
    setEditFactModalOpen(true);
  };

  const handleSaveFactCorrection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingFact) return;
    setSavingEdit(true);
    try {
      await api.updateFact(editingFact.id, editFactForm);
      setEditFactModalOpen(false);
      setEditingFact(null);
      await loadData();
    } catch (err: any) {
      alert(`Correction error: ${err.message}`);
    } finally {
      setSavingEdit(false);
    }
  };

  const handleReviewAsset = async (assetId: string, status: 'approved' | 'rejected') => {
    try {
      await api.reviewAsset(assetId, status);
      await loadData();
    } catch (err: any) {
      alert(`Review error: ${err.message}`);
    }
  };

  const handleReprocessSource = async (sourceId: string, sourceTitle: string) => {
    const ok = window.confirm(
      `Reprocess '${sourceTitle}' using Gemini?\n\n` +
      `Safety Guarantee:\n` +
      `• All Approved, Rejected, and Reviewer-Edited records will be preserved.\n` +
      `• Only unreviewed machine-generated candidates will be safely refreshed.\n\n` +
      `Do you wish to proceed?`
    );
    if (!ok) return;

    setReprocessingId(sourceId);
    try {
      const updated = await api.reprocessSource(sourceId);
      alert(`Reprocessing complete!\n${updated.rules_count || 0} candidate rules and ${updated.facts_count || 0} facts now in Pending Review.`);
      await loadData();
    } catch (err: any) {
      alert(`Reprocessing error: ${err.message}`);
    } finally {
      setReprocessingId(null);
    }
  };

  const getSourceStatusBadge = (sourceStatus?: string) => {
    switch (sourceStatus) {
      case 'approved':
        return <span style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', border: '1px solid rgba(59, 130, 246, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>Source: Approved</span>;
      case 'pending_review':
        return <span style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', border: '1px solid rgba(245, 158, 11, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>Source: Pending Review</span>;
      case 'expired':
        return <span style={{ background: 'rgba(234, 88, 12, 0.15)', color: '#fb923c', border: '1px solid rgba(234, 88, 12, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>Source: Expired</span>;
      case 'rejected':
        return <span style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>Source: Rejected</span>;
      default:
        return null;
    }
  };

  const getEvidenceValidationBadge = (status?: string, pageNum?: number) => {
    switch (status) {
      case 'verified_exact':
        return <span style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>Verified (Page {pageNum || 'Doc'})</span>;
      case 'verified_fuzzy':
        return <span style={{ background: 'rgba(20, 184, 166, 0.15)', color: '#2dd4bf', border: '1px solid rgba(20, 184, 166, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>Fuzzy Match (Page {pageNum || 'Doc'})</span>;
      case 'page_mismatch':
        return <span style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', border: '1px solid rgba(245, 158, 11, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>Page Mismatch</span>;
      case 'unverified':
        return <span style={{ background: 'rgba(100, 116, 139, 0.2)', color: '#94a3b8', border: '1px solid rgba(100, 116, 139, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>Unverified Citation</span>;
      default:
        return null;
    }
  };

  const filteredRules = rules.filter(r => statusFilter === 'all' || r.status === statusFilter);
  const filteredFacts = facts.filter(f => statusFilter === 'all' || f.status === statusFilter);
  const filteredAssets = assets.filter(a => statusFilter === 'all' || a.status === statusFilter);

  return (
    <div>
      {/* Header */}
      <div className="flex-between" style={{ marginBottom: 20 }}>
        <div>
          <h1 className="title-xl">Knowledge Library & Brand Governance</h1>
          <p className="text-sub">
            Brand guidelines, approved product facts, and creative assets. Only <strong>Approved</strong> records are authoritative.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={() => setShowOnboardingGuide(!showOnboardingGuide)}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.82rem' }}
          >
            <HelpCircle size={15} color="#818cf8" />
            {showOnboardingGuide ? 'Hide Onboarding Guide' : 'Brand Setup Guide'}
            {showOnboardingGuide ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          <button
            onClick={() => {
              setUploadModalTab('required');
              setUploadModalOpen(true);
            }}
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: 8 }}
          >
            <Upload size={16} /> Onboard Brand Knowledge
          </button>
        </div>
      </div>

      {/* Brand Knowledge Onboarding & Requirements Guide (Collapsible) */}
      {showOnboardingGuide && (
        <div className="card" style={{
          marginBottom: 24,
          padding: 24,
          background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.4) 0%, rgba(19, 27, 46, 0.8) 100%)',
          border: '1px solid rgba(99, 102, 241, 0.35)',
          borderRadius: 14,
          boxShadow: '0 10px 30px rgba(0,0,0,0.3)'
        }}>
          <div className="flex-between" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 0 12px rgba(99,102,241,0.4)'
              }}>
                <Sparkles size={20} color="#fff" />
              </div>
              <div>
                <h2 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.01em', margin: 0 }}>
                  Organisation Brand-Knowledge Onboarding
                </h2>
                <span style={{ fontSize: '0.78rem', color: '#cbd5e1' }}>
                  What your organisation needs to provide before automated governance checking
                </span>
              </div>
            </div>
            <button
              onClick={() => {
                setUploadModalTab('required');
                setUploadModalOpen(true);
              }}
              className="btn btn-primary btn-sm"
              style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', padding: '8px 16px' }}
            >
              <Upload size={14} /> Start Onboarding Upload
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: 18, marginBottom: 18 }}>
            {/* Required Box */}
            <div style={{
              padding: 16,
              borderRadius: 10,
              background: 'rgba(99, 102, 241, 0.08)',
              border: '1px solid rgba(99, 102, 241, 0.25)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <span style={{ background: '#6366f1', color: '#fff', fontSize: '0.7rem', fontWeight: 800, padding: '2px 8px', borderRadius: 4, textTransform: 'uppercase' }}>
                  Required Minimum (2 Items)
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#fff', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <FileCheck2 size={16} color="#818cf8" /> 1. Brand guidelines (PDF)
                  </div>
                  <p style={{ fontSize: '0.79rem', color: '#cbd5e1', marginTop: 4, lineHeight: 1.45 }}>
                    Upload your brand guidelines in PDF format. Your document should describe your brand identity, colours, typography, tone of voice, messaging restrictions, logo usage, accessibility requirements, and any relevant claims or promotional rules.
                  </p>
                  <div style={{ fontSize: '0.75rem', color: '#a5b4fc', marginTop: 4, fontStyle: 'italic' }}>
                    Note: You can use your organisation's existing guidelines document; you do not need to rewrite everything in a special template.
                  </div>
                </div>

                <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 10 }}>
                  <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#fff', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <ImageIcon size={16} color="#818cf8" /> 2. Official brand logo
                  </div>
                  <p style={{ fontSize: '0.79rem', color: '#cbd5e1', marginTop: 4, lineHeight: 1.45 }}>
                    Upload the official logo that represents your brand. Inkloom AI uses it as a reference for logo identification and visual-consistency checks.
                  </p>
                  <div style={{ fontSize: '0.74rem', color: 'var(--text-dim)', marginTop: 4 }}>
                    Preferred: SVG or PNG (transparent background). Also supported: JPG/JPEG, WebP (up to 25MB).
                  </div>
                </div>
              </div>
            </div>

            {/* Optional Box */}
            <div style={{
              padding: 16,
              borderRadius: 10,
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid var(--border-subtle)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <span style={{ background: 'rgba(255,255,255,0.08)', color: 'var(--text-muted)', fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 4, textTransform: 'uppercase' }}>
                  Optional Inputs (Only When Needed)
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.79rem', color: '#cbd5e1' }}>
                <div>
                  <strong style={{ color: '#fff' }}>Product facts and approved claims:</strong>
                  <p style={{ margin: '2px 0 0 0', color: 'var(--text-muted)', fontSize: '0.76rem', lineHeight: 1.4 }}>
                    Product names, approved wording, prices or pack sizes in advertisements, nutritional data only when nutritional claims need verification, and promotion details.
                  </p>
                  <span style={{ fontSize: '0.73rem', color: '#fbbf24', display: 'block', marginTop: 3 }}>
                    You do not need to provide a complete product catalogue or nutrition table unless you want Inkloom AI to verify those details.
                  </span>
                </div>
                <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 8 }}>
                  <strong style={{ color: '#fff' }}>Approved reference assets:</strong>
                  <p style={{ margin: '2px 0 0 0', color: 'var(--text-muted)', fontSize: '0.76rem', lineHeight: 1.4 }}>
                    Product photographs and approved campaign creatives. These assets are optional but needed for reliable matching against specific approved creative assets.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Sample Document & Missing Info Policy Row */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1.2fr 1fr',
            gap: 14,
            padding: '12px 16px',
            borderRadius: 8,
            background: 'rgba(0, 0, 0, 0.25)',
            border: '1px solid rgba(255, 255, 255, 0.08)'
          }}>
            {/* Sample PDF Link & Note */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <button
                  onClick={handleViewSamplePdf}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#818cf8',
                    cursor: 'pointer',
                    fontWeight: 700,
                    fontSize: '0.82rem',
                    padding: 0,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    textDecoration: 'underline'
                  }}
                  title="Click to view or download sample brand guidelines reference PDF"
                >
                  <Download size={14} /> View sample brand guidelines (PDF)
                </button>
              </div>
              <p style={{ fontSize: '0.74rem', color: 'var(--text-dim)', margin: 0, lineHeight: 1.4 }}>
                This sample illustrates the type of information Inkloom AI can use. It is a reference, not a mandatory template. Replace the fictional brand information with your organisation's actual policies and approved facts.
              </p>
            </div>

            {/* Missing Info Policy */}
            <div style={{ borderLeft: '1px solid rgba(255, 255, 255, 0.08)', paddingLeft: 14 }}>
              <div style={{ fontSize: '0.74rem', fontWeight: 700, color: '#fbbf24', marginBottom: 2 }}>
                Missing-Information Behaviour:
              </div>
              <p style={{ fontSize: '0.73rem', color: '#cbd5e1', margin: 0, lineHeight: 1.35 }}>
                Inkloom AI checks content against the information your organisation provides. When a claim or requirement cannot be verified against the supplied guidelines, the result will say: <em>"Unable to verify against the supplied guidelines; needs user review."</em> Missing information will not be treated as proof of compliance.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Pending Knowledge Notice */}
      <div style={{ padding: '12px 18px', background: 'rgba(245, 158, 11, 0.08)', borderRadius: 10, border: '1px solid rgba(245, 158, 11, 0.25)', marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
        <AlertCircle size={20} color="#fbbf24" />
        <div style={{ fontSize: '0.82rem', color: '#fef3c7' }}>
          <strong>Core Governance Principle:</strong> Newly uploaded documents and Gemini-extracted candidates start in a <strong>pending review</strong> state. Uploading never auto-approves knowledge. Knowledge Reviewers can correct, approve, or reject candidate facts before the governance engine uses them.
        </div>
      </div>

      {/* Tabs and Filter Bar */}
      <div className="flex-between" style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12, marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => setActiveTab('rules')}
            className={`tab-btn ${activeTab === 'rules' ? 'active' : ''}`}
          >
            Brand Rules ({rules.length})
          </button>
          <button
            onClick={() => setActiveTab('facts')}
            className={`tab-btn ${activeTab === 'facts' ? 'active' : ''}`}
          >
            Product Facts & Claims ({facts.length})
          </button>
          <button
            onClick={() => setActiveTab('assets')}
            className={`tab-btn ${activeTab === 'assets' ? 'active' : ''}`}
          >
            Brand Assets ({assets.length})
          </button>
          <button
            onClick={() => setActiveTab('sources')}
            className={`tab-btn ${activeTab === 'sources' ? 'active' : ''}`}
          >
            Uploaded Sources ({sources.length})
          </button>
        </div>

        {/* Status Filter and Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {isReviewer && (
            <button
              onClick={handleOpenAddRule}
              className="btn btn-primary"
              style={{ padding: '6px 12px', fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <Plus size={14} />
              Add Rule
            </button>
          )}
          <Filter size={14} color="var(--text-dim)" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="select"
            style={{ width: 'auto', padding: '6px 12px', fontSize: '0.8rem' }}
          >
            <option value="all">All Statuses</option>
            <option value="pending_review">Pending Review</option>
            <option value="approved">Approved Only</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      </div>

      {/* Tab 1: Brand Rules */}
      {activeTab === 'rules' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {filteredRules.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-dim)' }}>
              No rules found for filter '{statusFilter}'.
            </div>
          ) : (
            filteredRules.map((rule) => (
              <div key={rule.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', border: rule.is_corrected ? '1px solid rgba(168, 85, 247, 0.4)' : undefined }}>
                <div style={{ flex: 1 }}>
                  {/* Header badges */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    {rule.rule_code && (
                      <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.85rem', color: '#38bdf8', background: 'rgba(56, 189, 248, 0.1)', padding: '2px 8px', borderRadius: 4 }}>
                        {rule.rule_code}
                      </span>
                    )}
                    <span style={{ fontWeight: 700, fontSize: '1rem', color: '#fff' }}>{rule.title}</span>
                    <StatusBadge status={rule.status} />
                    {getExtractionMethodBadge(rule)}
                    {getSourceStatusBadge(rule.source_status)}
                    {getEvidenceValidationBadge(rule.evidence_validation, rule.page_number)}
                    {rule.is_corrected && (
                      <span style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>
                        Reviewer Edited
                      </span>
                    )}
                    <span className={`badge badge-${rule.severity === 'critical' ? 'danger' : 'warning'}`}>
                      {rule.severity}
                    </span>
                    <span className="badge badge-neutral">
                      {rule.rule_type.replace(/_/g, ' ')}
                    </span>
                  </div>

                  {/* Statement */}
                  <div style={{ marginTop: 10, fontSize: '0.88rem', color: '#f1f5f9', lineHeight: 1.5 }}>
                    <strong>Requirement:</strong> {rule.explanation}
                  </div>

                  {/* Rationale / Why it matters */}
                  {rule.rationale && (
                    <div style={{ marginTop: 6, fontSize: '0.82rem', color: '#94a3b8' }}>
                      <strong style={{ color: '#cbd5e1' }}>Rationale:</strong> {rule.rationale}
                    </div>
                  )}

                  {/* Evidence Passage */}
                  {rule.evidence_passage && (
                    <div style={{ marginTop: 8, padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 6, borderLeft: '3px solid #818cf8', fontSize: '0.8rem', color: '#cbd5e1', fontStyle: 'italic' }}>
                      <Quote size={12} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle', color: '#818cf8' }} />
                      "{rule.evidence_passage}"
                    </div>
                  )}

                  {/* Uncertainty / Warning notice */}
                  {rule.uncertainty_notes && (
                    <div style={{ marginTop: 8, padding: '6px 10px', background: 'rgba(245, 158, 11, 0.1)', borderRadius: 4, fontSize: '0.78rem', color: '#fbbf24', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <AlertTriangle size={14} />
                      <span>{rule.uncertainty_notes}</span>
                    </div>
                  )}

                  {/* Metadata line */}
                  <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: '0.75rem', color: 'var(--text-dim)', flexWrap: 'wrap' }}>
                    <div>Pattern: <code style={{ color: '#a5b4fc', background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: 4 }}>{rule.pattern}</code></div>
                    <div>Citation: <span style={{ color: 'var(--text-muted)' }}>{rule.source_citation || 'Brand Guidelines'}</span></div>
                    {rule.reviewed_at && (
                      <div>Reviewed: <span style={{ color: 'var(--text-muted)' }}>{new Date(rule.reviewed_at).toLocaleDateString()}</span></div>
                    )}
                  </div>
                  {rule.review_notes && (
                    <div style={{ marginTop: 6, fontSize: '0.75rem', color: '#94a3b8', fontStyle: 'italic' }}>
                      Review Notes: "{rule.review_notes}"
                    </div>
                  )}
                </div>

                {/* Reviewer Action Buttons */}
                {isReviewer && rule.status === 'pending_review' && (
                  <div style={{ display: 'flex', gap: 8, marginLeft: 16 }}>
                    <button
                      onClick={() => handleOpenEditRule(rule)}
                      className="btn btn-secondary"
                      style={{ padding: '6px 10px', fontSize: '0.75rem' }}
                      title="Correct rule wording or fields before approving"
                    >
                      <Edit3 size={13} /> Correct
                    </button>
                    <button
                      onClick={() => handleReviewRule(rule.id, 'approved')}
                      className="btn btn-success"
                      style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                    >
                      <Check size={14} /> Approve Rule
                    </button>
                    <button
                      onClick={() => handleReviewRule(rule.id, 'rejected')}
                      className="btn btn-danger"
                      style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                    >
                      <X size={14} /> Reject
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 2: Product Facts */}
      {activeTab === 'facts' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {filteredFacts.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-dim)' }}>
              No product facts found for filter '{statusFilter}'.
            </div>
          ) : (
            filteredFacts.map((fact) => (
              <div key={fact.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', border: fact.is_corrected ? '1px solid rgba(168, 85, 247, 0.4)' : undefined }}>
                <div style={{ flex: 1 }}>
                  {/* Header badges */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    {fact.product_id && (
                      <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.85rem', color: '#38bdf8', background: 'rgba(56, 189, 248, 0.1)', padding: '2px 8px', borderRadius: 4 }}>
                        {fact.product_id}
                      </span>
                    )}
                    <span style={{ fontWeight: 700, fontSize: '0.98rem', color: '#fff' }}>
                      {fact.product_name} — {fact.fact_key}
                    </span>
                    <StatusBadge status={fact.status} />
                    {getSourceStatusBadge(fact.source_status)}
                    {getEvidenceValidationBadge(fact.evidence_validation, fact.page_number)}
                    {fact.is_corrected && (
                      <span style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.3)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>
                        Reviewer Edited
                      </span>
                    )}
                    <span className="badge badge-info">{fact.category}</span>
                  </div>

                  {/* Specification Value */}
                  <div style={{ marginTop: 10, fontSize: '0.92rem', color: '#e2e8f0', fontWeight: 600 }}>
                    Value / Decision: <span style={{ color: fact.value_status === 'missing_not_provided' ? '#fbbf24' : '#34d399' }}>"{fact.fact_value}"</span>
                  </div>

                  {/* Supporting Evidence */}
                  {fact.supporting_evidence && (
                    <div style={{ marginTop: 8, padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 6, borderLeft: '3px solid #10b981', fontSize: '0.8rem', color: '#cbd5e1', fontStyle: 'italic' }}>
                      <Quote size={12} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle', color: '#10b981' }} />
                      "{fact.supporting_evidence}"
                    </div>
                  )}

                  {/* Data Gap / Uncertainty Notice */}
                  {fact.uncertainty_notes && (
                    <div style={{ marginTop: 8, padding: '6px 10px', background: 'rgba(245, 158, 11, 0.1)', borderRadius: 4, fontSize: '0.78rem', color: '#fbbf24', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <AlertTriangle size={14} />
                      <span>{fact.uncertainty_notes}</span>
                    </div>
                  )}

                  {/* Metadata line */}
                  <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: '0.75rem', color: 'var(--text-dim)', flexWrap: 'wrap' }}>
                    <div>Citation: <span style={{ color: 'var(--text-muted)' }}>{fact.source_citation || 'Product Knowledge Spec'}</span></div>
                    {fact.valid_until && (
                      <div>Valid Until: <span style={{ color: '#f59e0b' }}>{new Date(fact.valid_until).toLocaleDateString()}</span></div>
                    )}
                  </div>
                  {fact.review_notes && (
                    <div style={{ marginTop: 6, fontSize: '0.75rem', color: '#94a3b8', fontStyle: 'italic' }}>
                      Reviewer Note: "{fact.review_notes}"
                    </div>
                  )}
                </div>

                {isReviewer && fact.status === 'pending_review' && (
                  <div style={{ display: 'flex', gap: 8, marginLeft: 16 }}>
                    <button
                      onClick={() => handleOpenEditFact(fact)}
                      className="btn btn-secondary"
                      style={{ padding: '6px 10px', fontSize: '0.75rem' }}
                      title="Correct fact value or specification before approving"
                    >
                      <Edit3 size={13} /> Correct
                    </button>
                    <button
                      onClick={() => handleReviewFact(fact.id, 'approved')}
                      className="btn btn-success"
                      style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                    >
                      <Check size={14} /> Approve Fact
                    </button>
                    <button
                      onClick={() => handleReviewFact(fact.id, 'rejected')}
                      className="btn btn-danger"
                      style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                    >
                      <X size={14} /> Reject
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 3: Brand Assets */}
      {activeTab === 'assets' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
          {filteredAssets.length === 0 ? (
            <div className="card" style={{ gridColumn: '1 / -1', textAlign: 'center', padding: 40, color: 'var(--text-dim)' }}>
              No brand assets found for filter '{statusFilter}'.
            </div>
          ) : (
            filteredAssets.map((asset) => (
              <div key={asset.id} className="card">
                <div className="flex-between" style={{ marginBottom: 10 }}>
                  <span className="badge badge-neutral">{asset.asset_type.replace(/_/g, ' ')}</span>
                  <StatusBadge status={asset.status} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#fff', marginBottom: 4 }}>
                  {asset.asset_name}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginBottom: 12 }}>
                  {asset.mime_type} {asset.width ? `• ${asset.width}x${asset.height}px` : ''}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Clearance: <strong>{asset.min_clearance_px || 20}px</strong> | Aspect Ratio: <strong>{asset.aspect_ratio || 'N/A'}</strong>
                </div>

                {isReviewer && asset.status === 'pending_review' && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                    <button
                      onClick={() => handleReviewAsset(asset.id, 'approved')}
                      className="btn btn-success"
                      style={{ flex: 1, padding: '6px 8px', fontSize: '0.75rem' }}
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleReviewAsset(asset.id, 'rejected')}
                      className="btn btn-danger"
                      style={{ flex: 1, padding: '6px 8px', fontSize: '0.75rem' }}
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 4: Uploaded Sources */}
      {activeTab === 'sources' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {sources.map((src) => (
            <div key={src.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <FileText size={18} color="#818cf8" />
                  <span style={{ fontWeight: 700, fontSize: '1rem', color: '#fff' }}>{src.title}</span>
                  <StatusBadge status={src.status} />
                  <span style={{ background: 'rgba(255,255,255,0.06)', color: '#cbd5e1', padding: '2px 6px', borderRadius: 4, fontSize: '0.72rem' }}>
                    v{src.version}
                  </span>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
                  Filename: <span style={{ color: '#fff', fontWeight: 600 }}>{src.filename}</span> | Size: {(src.file_size_bytes / 1024).toFixed(1)} KB | Uploaded: {new Date(src.created_at).toLocaleDateString()}
                </div>
                {src.extracted_summary && (
                  <div style={{ marginTop: 8, fontSize: '0.8rem', color: '#a5b4fc', lineHeight: 1.4 }}>
                    {src.extracted_summary}
                  </div>
                )}
              </div>

              <div style={{ textAlign: 'right', marginLeft: 20 }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 8 }}>
                  <div>Rules Extracted: <strong>{src.rules_count || 0}</strong></div>
                  <div>Facts Extracted: <strong>{src.facts_count || 0}</strong></div>
                </div>

                <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                  {src.filename.toLowerCase().endsWith('.pdf') && (
                    <button
                      onClick={() => handleViewSourceText(src.id, src.title)}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.75rem', padding: '6px 12px', display: 'inline-flex', alignItems: 'center', gap: 6 }}
                      title="View extracted document text per page"
                    >
                      <FileText size={13} />
                      View Document Text
                    </button>
                  )}

                  {isReviewer && src.filename.toLowerCase().endsWith('.pdf') && (
                    <button
                      onClick={() => handleReprocessSource(src.id, src.title)}
                      disabled={reprocessingId === src.id}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.75rem', padding: '6px 12px', display: 'inline-flex', alignItems: 'center', gap: 6 }}
                      title="Safely re-run Gemini extraction on this document (preserves reviewed knowledge)"
                    >
                      <RefreshCw size={13} className={reprocessingId === src.id ? 'spin' : ''} />
                      {reprocessingId === src.id ? 'Reprocessing...' : 'Reprocess with Gemini'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit Rule Correction Modal */}
      {editRuleModalOpen && editingRule && (
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
          <div className="card" style={{ width: 560, background: '#131b2e', border: '1px solid rgba(168, 85, 247, 0.4)' }}>
            <div className="flex-between" style={{ marginBottom: 16 }}>
              <div>
                <h2 className="title-md">Correct Extracted Brand Rule</h2>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                  Rule Code: {editingRule.rule_code || editingRule.id} | Page {editingRule.page_number || 'N/A'}
                </span>
              </div>
              <button onClick={() => setEditRuleModalOpen(false)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSaveRuleCorrection}>
              <div className="form-group">
                <label className="form-label">Rule Title</label>
                <input
                  type="text"
                  value={editRuleForm.title}
                  onChange={(e) => setEditRuleForm({ ...editRuleForm, title: e.target.value })}
                  className="input"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Rule Requirement / Statement</label>
                <textarea
                  value={editRuleForm.explanation}
                  onChange={(e) => setEditRuleForm({ ...editRuleForm, explanation: e.target.value })}
                  className="input"
                  rows={3}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Pattern / Keywords (comma-separated)</label>
                <input
                  type="text"
                  value={editRuleForm.pattern}
                  onChange={(e) => setEditRuleForm({ ...editRuleForm, pattern: e.target.value })}
                  className="input"
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Severity</label>
                  <select
                    value={editRuleForm.severity}
                    onChange={(e) => setEditRuleForm({ ...editRuleForm, severity: e.target.value })}
                    className="select"
                  >
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="warning">Warning / Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Rule Type</label>
                  <select
                    value={editRuleForm.rule_type}
                    onChange={(e) => setEditRuleForm({ ...editRuleForm, rule_type: e.target.value })}
                    className="select"
                  >
                    <option value="prohibited_word">Prohibited Word / Claim</option>
                    <option value="required_term">Required Term / Disclosure</option>
                    <option value="tone_guideline">Tone Guideline</option>
                    <option value="image_standard">Image / Asset Policy</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Reviewer Correction Notes</label>
                <input
                  type="text"
                  value={editRuleForm.review_notes}
                  onChange={(e) => setEditRuleForm({ ...editRuleForm, review_notes: e.target.value })}
                  placeholder="Explain what was corrected and why..."
                  className="input"
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
                <button type="button" onClick={() => setEditRuleModalOpen(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={savingEdit} className="btn btn-primary">
                  {savingEdit ? 'Saving...' : 'Save Correction'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Fact Correction Modal */}
      {editFactModalOpen && editingFact && (
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
          <div className="card" style={{ width: 560, background: '#131b2e', border: '1px solid rgba(168, 85, 247, 0.4)' }}>
            <div className="flex-between" style={{ marginBottom: 16 }}>
              <div>
                <h2 className="title-md">Correct Extracted Product Fact or Claim</h2>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                  Page {editingFact.page_number || 'N/A'} | Citation: {editingFact.source_citation}
                </span>
              </div>
              <button onClick={() => setEditFactModalOpen(false)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSaveFactCorrection}>
              <div className="form-group">
                <label className="form-label">Product Name / Group</label>
                <input
                  type="text"
                  value={editFactForm.product_name}
                  onChange={(e) => setEditFactForm({ ...editFactForm, product_name: e.target.value })}
                  className="input"
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Fact Attribute / Key</label>
                  <input
                    type="text"
                    value={editFactForm.fact_key}
                    onChange={(e) => setEditFactForm({ ...editFactForm, fact_key: e.target.value })}
                    className="input"
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Category</label>
                  <select
                    value={editFactForm.category}
                    onChange={(e) => setEditFactForm({ ...editFactForm, category: e.target.value })}
                    className="select"
                  >
                    <option value="nutrition">Nutrition</option>
                    <option value="ingredient">Ingredient & Allergens</option>
                    <option value="specification">Specification</option>
                    <option value="pricing">Pricing</option>
                    <option value="claim">Claim</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Specification Value / Claim Decision</label>
                <input
                  type="text"
                  value={editFactForm.fact_value}
                  onChange={(e) => setEditFactForm({ ...editFactForm, fact_value: e.target.value })}
                  className="input"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Reviewer Correction Notes</label>
                <input
                  type="text"
                  value={editFactForm.review_notes}
                  onChange={(e) => setEditFactForm({ ...editFactForm, review_notes: e.target.value })}
                  placeholder="Explain what was corrected..."
                  className="input"
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
                <button type="button" onClick={() => setEditFactModalOpen(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={savingEdit} className="btn btn-primary">
                  {savingEdit ? 'Saving...' : 'Save Correction'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Upload & Onboarding Modal */}
      {uploadModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.75)',
          backdropFilter: 'blur(10px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100,
          padding: 20
        }}>
          <div className="card" style={{
            width: '100%',
            maxWidth: 680,
            maxHeight: '92vh',
            overflowY: 'auto',
            background: '#131b2e',
            border: '1px solid rgba(255,255,255,0.18)',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
          }}>
            {/* Modal Header */}
            <div className="flex-between" style={{ marginBottom: 16, borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: 12 }}>
              <div>
                <h2 className="title-md" style={{ display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
                  <ShieldCheck size={22} color="#6366f1" />
                  Organisation Brand Setup & Onboarding
                </h2>
                <p className="text-sub" style={{ fontSize: '0.8rem', marginTop: 4, marginBottom: 0 }}>
                  Provide your brand knowledge baseline to establish governance rules and logo matching.
                </p>
              </div>
              <button
                onClick={() => {
                  setUploadModalOpen(false);
                  setUploadMsg(null);
                  setUploadStepMsg(null);
                }}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4 }}
                title="Close modal"
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Navigation Tabs */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 18, borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: 10 }}>
              <button
                type="button"
                onClick={() => {
                  setUploadModalTab('required');
                  setUploadMsg(null);
                }}
                style={{
                  background: uploadModalTab === 'required' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
                  border: uploadModalTab === 'required' ? '1px solid rgba(99, 102, 241, 0.5)' : '1px solid transparent',
                  color: uploadModalTab === 'required' ? '#a5b4fc' : '#94a3b8',
                  padding: '6px 14px',
                  borderRadius: 6,
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8
                }}
              >
                <span>Minimum Requirements</span>
                <span style={{
                  background: '#f43f5e',
                  color: '#fff',
                  fontSize: '0.65rem',
                  padding: '1px 6px',
                  borderRadius: 10,
                  fontWeight: 700
                }}>Required</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setUploadModalTab('optional');
                  setUploadMsg(null);
                }}
                style={{
                  background: uploadModalTab === 'optional' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
                  border: uploadModalTab === 'optional' ? '1px solid rgba(99, 102, 241, 0.5)' : '1px solid transparent',
                  color: uploadModalTab === 'optional' ? '#a5b4fc' : '#94a3b8',
                  padding: '6px 14px',
                  borderRadius: 6,
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8
                }}
              >
                <span>Facts & Reference Assets</span>
                <span style={{
                  background: 'rgba(255,255,255,0.1)',
                  color: '#cbd5e1',
                  fontSize: '0.65rem',
                  padding: '1px 6px',
                  borderRadius: 10
                }}>Optional</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setUploadModalTab('single');
                  setUploadMsg(null);
                }}
                style={{
                  background: uploadModalTab === 'single' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
                  border: uploadModalTab === 'single' ? '1px solid rgba(99, 102, 241, 0.5)' : '1px solid transparent',
                  color: uploadModalTab === 'single' ? '#a5b4fc' : '#94a3b8',
                  padding: '6px 14px',
                  borderRadius: 6,
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Single Document / Category
              </button>
            </div>

            {/* TAB 1: REQUIRED ONBOARDING (Brand Guidelines + Official Logo) */}
            {uploadModalTab === 'required' && (
              <form onSubmit={handleRequiredOnboard}>
                {/* Brand selection */}
                <div className="form-group" style={{ marginBottom: 16 }}>
                  <label className="form-label" style={{ fontWeight: 600 }}>Active Brand Workspace</label>
                  <select
                    value={selectedBrandId}
                    onChange={(e) => setSelectedBrandId(e.target.value)}
                    className="select"
                    disabled={uploading}
                  >
                    {brands.map(b => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </div>

                {/* 1. REQUIRED INPUT: Brand guidelines */}
                <div style={{
                  background: 'rgba(15, 23, 42, 0.65)',
                  border: '1px solid rgba(99, 102, 241, 0.3)',
                  borderRadius: 10,
                  padding: 16,
                  marginBottom: 16
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <FileText size={18} color="#6366f1" />
                      <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc', margin: 0 }}>
                        1. Brand guidelines
                      </h3>
                    </div>
                    <span style={{
                      background: 'rgba(244, 63, 94, 0.15)',
                      color: '#fb7185',
                      border: '1px solid rgba(244, 63, 94, 0.35)',
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: 12
                    }}>Required</span>
                  </div>

                  <p style={{ fontSize: '0.82rem', color: '#cbd5e1', lineHeight: 1.5, marginBottom: 8 }}>
                    Upload your brand guidelines in PDF format. Your document should describe your brand identity, colours, typography, tone of voice, messaging restrictions, logo usage, accessibility requirements, and any relevant claims or promotional rules.
                  </p>

                  <div style={{
                    background: 'rgba(99, 102, 241, 0.08)',
                    borderLeft: '3px solid #6366f1',
                    padding: '8px 12px',
                    borderRadius: 4,
                    fontSize: '0.78rem',
                    color: '#c7d2fe',
                    marginBottom: 10
                  }}>
                    You can use your organisation's existing guidelines document; you do not need to rewrite everything in a special template.
                  </div>

                  {/* Checklist */}
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#94a3b8', marginBottom: 4 }}>
                      Recommended contents checklist:
                    </div>
                    <ul style={{
                      margin: 0,
                      paddingLeft: 20,
                      fontSize: '0.76rem',
                      color: '#94a3b8',
                      lineHeight: 1.55
                    }}>
                      <li>Official brand and company names</li>
                      <li>Brand colours and typography</li>
                      <li>Logo usage and visual identity</li>
                      <li>Tone of voice and restricted terminology</li>
                      <li>Approved and prohibited messaging or claims</li>
                      <li>Promotional restrictions and mandatory disclosures</li>
                      <li>Relevant exceptions and escalation requirements</li>
                    </ul>
                    <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: 4, fontStyle: 'italic' }}>
                      Not every organisation needs product or nutritional data unless it wants those specific checks.
                    </div>
                  </div>

                  {/* Sample document link */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    background: 'rgba(30, 41, 59, 0.7)',
                    padding: '10px 12px',
                    borderRadius: 6,
                    border: '1px dashed rgba(99, 102, 241, 0.3)',
                    marginBottom: 12
                  }}>
                    <BookOpen size={18} color="#818cf8" style={{ marginTop: 2, flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                      <div>
                        <a
                          href="/samples/Willow_and_Vale_Brand_Governance_Manual_Sample.pdf"
                          onClick={handleViewSamplePdf}
                          style={{
                            color: '#818cf8',
                            fontSize: '0.82rem',
                            fontWeight: 600,
                            textDecoration: 'underline',
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4
                          }}
                        >
                          View sample brand guidelines (PDF)
                          <ExternalLink size={12} />
                        </a>
                      </div>
                      <p style={{ fontSize: '0.74rem', color: '#94a3b8', margin: '4px 0 0 0', lineHeight: 1.45 }}>
                        This sample illustrates the type of information Inkloom AI can use. It is a reference, not a mandatory template. Replace the fictional brand information with your organisation's actual policies and approved facts.
                      </p>
                    </div>
                  </div>

                  {/* File picker */}
                  <div>
                    <label className="form-label" style={{ fontSize: '0.78rem', color: '#cbd5e1' }}>
                      Select Brand Guidelines PDF (Max 25 MB)
                    </label>
                    <input
                      type="file"
                      accept=".pdf,application/pdf"
                      onChange={handleGuidelinesChange}
                      className="input"
                      disabled={uploading}
                    />
                    {guidelinesFile && (
                      <div style={{ fontSize: '0.75rem', color: '#34d399', marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <CheckCircle size={14} /> Selected: {guidelinesFile.name} ({(guidelinesFile.size / (1024 * 1024)).toFixed(2)} MB)
                      </div>
                    )}
                  </div>
                </div>

                {/* 2. REQUIRED INPUT: Official brand logo */}
                <div style={{
                  background: 'rgba(15, 23, 42, 0.65)',
                  border: '1px solid rgba(99, 102, 241, 0.3)',
                  borderRadius: 10,
                  padding: 16,
                  marginBottom: 16
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <ImageIcon size={18} color="#6366f1" />
                      <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc', margin: 0 }}>
                        2. Official brand logo
                      </h3>
                    </div>
                    <span style={{
                      background: 'rgba(244, 63, 94, 0.15)',
                      color: '#fb7185',
                      border: '1px solid rgba(244, 63, 94, 0.35)',
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: 12
                    }}>Required</span>
                  </div>

                  <p style={{ fontSize: '0.82rem', color: '#cbd5e1', lineHeight: 1.5, marginBottom: 8 }}>
                    Upload the official logo that represents your brand. Inkloom AI uses it as a reference for logo identification and visual-consistency checks.
                  </p>

                  <div style={{
                    fontSize: '0.78rem',
                    color: '#94a3b8',
                    marginBottom: 8,
                    background: 'rgba(15, 23, 42, 0.4)',
                    padding: '8px 10px',
                    borderRadius: 6
                  }}>
                    <div><strong>Preferred formats:</strong> SVG or PNG, preferably with a transparent background.</div>
                    <div style={{ marginTop: 2 }}><strong>Supported formats:</strong> SVG, PNG, JPG/JPEG, WebP (up to 25 MB).</div>
                    <div style={{ marginTop: 4, color: '#64748b', fontSize: '0.74rem' }}>
                      Alternate light, dark, or monochrome logo variants can be added later when available.
                    </div>
                  </div>

                  <div style={{
                    fontSize: '0.74rem',
                    color: '#f59e0b',
                    background: 'rgba(245, 158, 11, 0.08)',
                    borderLeft: '3px solid #f59e0b',
                    padding: '6px 10px',
                    borderRadius: 4,
                    marginBottom: 12
                  }}>
                    <strong>Visual Governance Note:</strong> The logo alone is not enough to verify every visual requirement. Reference assets improve matching, while uncertain results still need review.
                  </div>

                  {/* Logo File picker & Preview */}
                  <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
                    <div style={{ flex: 1 }}>
                      <label className="form-label" style={{ fontSize: '0.78rem', color: '#cbd5e1' }}>
                        Select Official Logo File
                      </label>
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/webp,image/svg+xml,.svg,.png,.jpg,.jpeg,.webp"
                        onChange={handleLogoChange}
                        className="input"
                        disabled={uploading}
                      />
                      {logoFile && (
                        <div style={{ fontSize: '0.75rem', color: '#34d399', marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                          <CheckCircle size={14} /> Selected: {logoFile.name} ({(logoFile.size / 1024).toFixed(1)} KB)
                        </div>
                      )}
                    </div>
                    {logoPreviewUrl && (
                      <div style={{
                        width: 64,
                        height: 64,
                        borderRadius: 6,
                        border: '1px solid rgba(255,255,255,0.2)',
                        background: '#1e293b',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        overflow: 'hidden',
                        flexShrink: 0
                      }}>
                        <img
                          src={logoPreviewUrl}
                          alt="Logo preview"
                          style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                        />
                      </div>
                    )}
                  </div>
                </div>

                {/* Missing-Information Behaviour Banner */}
                <div style={{
                  background: 'rgba(15, 23, 42, 0.7)',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                  borderRadius: 8,
                  padding: '10px 14px',
                  marginBottom: 16,
                  display: 'flex',
                  gap: 10,
                  alignItems: 'flex-start'
                }}>
                  <AlertCircle size={18} color="#f59e0b" style={{ flexShrink: 0, marginTop: 2 }} />
                  <div style={{ fontSize: '0.76rem', color: '#cbd5e1', lineHeight: 1.5 }}>
                    <strong style={{ color: '#fbbf24' }}>Missing-Information Behaviour:</strong> Inkloom AI checks content against the information your organisation provides. When a claim or requirement cannot be verified against the supplied guidelines, the result will say: <em>"Unable to verify against the supplied guidelines; needs user review."</em> Missing information will not be treated as proof of compliance.
                  </div>
                </div>

                {/* Progress / Step indicator */}
                {uploadStepMsg && (
                  <div style={{
                    padding: '8px 12px',
                    borderRadius: 6,
                    fontSize: '0.8rem',
                    marginBottom: 12,
                    background: 'rgba(99, 102, 241, 0.15)',
                    border: '1px solid rgba(99, 102, 241, 0.3)',
                    color: '#c7d2fe',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8
                  }}>
                    <div style={{
                      width: 12,
                      height: 12,
                      border: '2px solid #818cf8',
                      borderTopColor: 'transparent',
                      borderRadius: '50%',
                      animation: 'spin 1s linear infinite'
                    }} />
                    <span>{uploadStepMsg}</span>
                  </div>
                )}

                {/* Upload status message */}
                {uploadMsg && (
                  <div style={{
                    padding: 12,
                    borderRadius: 6,
                    fontSize: '0.8rem',
                    marginBottom: 14,
                    background: uploadMsg.type === 'success' ? 'rgba(16,185,129,0.15)' : 'rgba(244,63,94,0.15)',
                    border: `1px solid ${uploadMsg.type === 'success' ? 'rgba(16,185,129,0.3)' : 'rgba(244,63,94,0.3)'}`,
                    color: uploadMsg.type === 'success' ? '#34d399' : '#fb7185'
                  }}>
                    <div style={{ fontWeight: 600 }}>{uploadMsg.text}</div>
                    {uploadMsg.details && uploadMsg.details.length > 0 && (
                      <ul style={{ margin: '6px 0 0 0', paddingLeft: 18, fontSize: '0.75rem', lineHeight: 1.4 }}>
                        {uploadMsg.details.map((d, i) => (
                          <li key={i}>{d}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {/* Actions */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
                  <button
                    type="button"
                    onClick={() => {
                      setUploadModalOpen(false);
                      setUploadMsg(null);
                      setUploadStepMsg(null);
                    }}
                    className="btn btn-secondary"
                    disabled={uploading}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={uploading || (!guidelinesFile && !logoFile)}
                    className="btn btn-primary"
                    style={{ display: 'flex', alignItems: 'center', gap: 8 }}
                  >
                    <Upload size={16} />
                    {uploading ? (uploadStepMsg || 'Uploading & Extracting...') : 'Upload Baseline Knowledge'}
                  </button>
                </div>
              </form>
            )}

            {/* TAB 2: OPTIONAL INPUTS (Product Facts, Claims, Reference Assets) */}
            {uploadModalTab === 'optional' && (
              <form onSubmit={handleOptionalUpload}>
                <div style={{
                  background: 'rgba(30, 41, 59, 0.4)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 8,
                  padding: 12,
                  marginBottom: 16,
                  fontSize: '0.8rem',
                  color: '#94a3b8',
                  lineHeight: 1.5
                }}>
                  <strong style={{ color: '#f8fafc' }}>Optional Inputs — Requested only when needed for additional checks.</strong><br />
                  You do not need to provide these unless your brand needs specific product specifications, nutritional claims verification, or visual matching against approved creatives.
                </div>

                <div className="form-group" style={{ marginBottom: 14 }}>
                  <label className="form-label">Brand Workspace</label>
                  <select
                    value={selectedBrandId}
                    onChange={(e) => setSelectedBrandId(e.target.value)}
                    className="select"
                    disabled={uploading}
                  >
                    {brands.map(b => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group" style={{ marginBottom: 14 }}>
                  <label className="form-label">Optional Resource Category</label>
                  <select
                    value={optionalType}
                    onChange={(e) => setOptionalType(e.target.value)}
                    className="select"
                    disabled={uploading}
                  >
                    <option value="pdf_product_knowledge">Product Facts & Approved Claims (PDF/Text)</option>
                    <option value="supporting_doc">Supporting Evidence Document (CSV/XLSX/PDF)</option>
                    <option value="brand_asset_image">Approved Reference Asset (Image/Creative)</option>
                  </select>
                </div>

                {/* Explanatory breakdown based on category */}
                <div style={{
                  background: 'rgba(15, 23, 42, 0.65)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 8,
                  padding: 14,
                  marginBottom: 16
                }}>
                  {optionalType !== 'brand_asset_image' ? (
                    <div>
                      <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc', margin: '0 0 6px 0' }}>
                        Product facts and approved claims
                      </h4>
                      <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.55 }}>
                        <li>Product names and variants</li>
                        <li>Approved wording and standard messaging</li>
                        <li>Prices or pack sizes displayed in advertisements</li>
                        <li>Nutritional data only when nutritional claims need verification</li>
                        <li>Promotion details when promotion checking is required</li>
                      </ul>
                      <div style={{
                        marginTop: 8,
                        fontSize: '0.76rem',
                        color: '#a5b4fc',
                        background: 'rgba(99, 102, 241, 0.1)',
                        padding: '6px 10px',
                        borderRadius: 4
                      }}>
                        You do not need to provide a complete product catalogue or nutrition table unless you want Inkloom AI to verify those details.
                      </div>
                    </div>
                  ) : (
                    <div>
                      <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc', margin: '0 0 6px 0' }}>
                        Approved reference assets
                      </h4>
                      <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.55 }}>
                        <li>Product photographs and pack shots</li>
                        <li>Approved campaign creatives and key visuals</li>
                        <li>Other visual assets the organisation wants checked</li>
                      </ul>
                      <div style={{
                        marginTop: 8,
                        fontSize: '0.76rem',
                        color: '#a5b4fc',
                        background: 'rgba(99, 102, 241, 0.1)',
                        padding: '6px 10px',
                        borderRadius: 4
                      }}>
                        These assets are optional but needed for reliable matching against specific approved creative assets.
                      </div>
                    </div>
                  )}
                </div>

                <div className="form-group" style={{ marginBottom: 16 }}>
                  <label className="form-label">
                    Select File {optionalType === 'brand_asset_image' ? '(SVG, PNG, JPG, WEBP)' : '(PDF, CSV, TXT)'}
                  </label>
                  <input
                    type="file"
                    accept={
                      optionalType === 'brand_asset_image'
                        ? 'image/png,image/jpeg,image/webp,image/svg+xml'
                        : '.pdf,.csv,.txt,application/pdf'
                    }
                    onChange={(e) => setOptionalFile(e.target.files?.[0] || null)}
                    className="input"
                    disabled={uploading}
                    required
                  />
                  {optionalFile && (
                    <div style={{ fontSize: '0.75rem', color: '#34d399', marginTop: 4 }}>
                      Selected: {optionalFile.name} ({(optionalFile.size / (1024 * 1024)).toFixed(2)} MB)
                    </div>
                  )}
                </div>

                {uploadMsg && (
                  <div style={{
                    padding: 10,
                    borderRadius: 6,
                    fontSize: '0.8rem',
                    marginBottom: 14,
                    background: uploadMsg.type === 'success' ? 'rgba(16,185,129,0.15)' : 'rgba(244,63,94,0.15)',
                    border: `1px solid ${uploadMsg.type === 'success' ? 'rgba(16,185,129,0.3)' : 'rgba(244,63,94,0.3)'}`,
                    color: uploadMsg.type === 'success' ? '#34d399' : '#fb7185'
                  }}>
                    {uploadMsg.text}
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
                  <button
                    type="button"
                    onClick={() => {
                      setUploadModalOpen(false);
                      setUploadMsg(null);
                    }}
                    className="btn btn-secondary"
                    disabled={uploading}
                  >
                    Close
                  </button>
                  <button
                    type="submit"
                    disabled={uploading || !optionalFile}
                    className="btn btn-primary"
                  >
                    {uploading ? 'Uploading...' : 'Upload Optional Resource'}
                  </button>
                </div>
              </form>
            )}

            {/* TAB 3: SINGLE FILE / LEGACY */}
            {uploadModalTab === 'single' && (
              <form onSubmit={handleUpload}>
                <div className="form-group" style={{ marginBottom: 14 }}>
                  <label className="form-label">Knowledge Category</label>
                  <select
                    value={uploadType}
                    onChange={(e) => setUploadType(e.target.value)}
                    className="select"
                    disabled={uploading}
                  >
                    <option value="pdf_brand_guidelines">PDF Brand Guidelines</option>
                    <option value="pdf_product_knowledge">PDF Product Knowledge & Specs</option>
                    <option value="supporting_doc">Supporting Evidence Document</option>
                    <option value="brand_asset_image">Brand Asset / Creative Image</option>
                  </select>
                </div>

                <div className="form-group" style={{ marginBottom: 14 }}>
                  <label className="form-label">Brand</label>
                  <select
                    value={selectedBrandId}
                    onChange={(e) => setSelectedBrandId(e.target.value)}
                    className="select"
                    disabled={uploading}
                  >
                    {brands.map(b => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group" style={{ marginBottom: 16 }}>
                  <label className="form-label">Select File (PDF, PNG, JPG, WEBP, SVG)</label>
                  <input
                    type="file"
                    accept=".pdf,image/png,image/jpeg,image/webp,image/svg+xml"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    className="input"
                    disabled={uploading}
                    required
                  />
                  {uploadFile && (
                    <div style={{ fontSize: '0.75rem', color: '#34d399', marginTop: 4 }}>
                      Selected: {uploadFile.name}
                    </div>
                  )}
                </div>

                {uploadMsg && (
                  <div style={{
                    padding: 10,
                    borderRadius: 6,
                    fontSize: '0.8rem',
                    marginBottom: 14,
                    background: uploadMsg.type === 'success' ? 'rgba(16,185,129,0.15)' : 'rgba(244,63,94,0.15)',
                    border: `1px solid ${uploadMsg.type === 'success' ? 'rgba(16,185,129,0.3)' : 'rgba(244,63,94,0.3)'}`,
                    color: uploadMsg.type === 'success' ? '#34d399' : '#fb7185'
                  }}>
                    {uploadMsg.text}
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
                  <button
                    type="button"
                    onClick={() => {
                      setUploadModalOpen(false);
                      setUploadMsg(null);
                    }}
                    className="btn btn-secondary"
                    disabled={uploading}
                  >
                    Close
                  </button>
                  <button type="submit" disabled={uploading || !uploadFile} className="btn btn-primary">
                    {uploading ? 'Processing Extraction...' : 'Upload & Extract Candidates'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Manual Rule Creation Modal */}
      {addRuleModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 110,
          padding: 20
        }}>
          <div className="card" style={{ width: '100%', maxWidth: 580, maxHeight: '90vh', overflowY: 'auto', background: '#131b2e', border: '1px solid rgba(99, 102, 241, 0.4)' }}>
            <div className="flex-between" style={{ marginBottom: 16 }}>
              <div>
                <h2 className="title-md">Create Brand Governance Rule</h2>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: 2 }}>
                  Rules start in <strong style={{ color: '#fbbf24' }}>Pending Review</strong> and must be verified by a human reviewer.
                </div>
              </div>
              <button
                onClick={() => setAddRuleModalOpen(false)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4 }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveNewRule}>
              <div className="form-group" style={{ marginBottom: 12 }}>
                <label className="form-label">Rule Title *</label>
                <input
                  type="text"
                  value={newRuleForm.title}
                  onChange={(e) => setNewRuleForm({ ...newRuleForm, title: e.target.value })}
                  placeholder="e.g. Unsupported Performance Claims"
                  className="input"
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div className="form-group">
                  <label className="form-label">Rule Type *</label>
                  <select
                    value={newRuleForm.rule_type}
                    onChange={(e) => setNewRuleForm({ ...newRuleForm, rule_type: e.target.value })}
                    className="select"
                  >
                    <option value="prohibited_word">Prohibited Words / Phrases</option>
                    <option value="required_term">Required Terms / Disclosures</option>
                    <option value="claim_policy">Claim Substantiation Policy</option>
                    <option value="tone_guideline">Tone & Voice Guideline</option>
                    <option value="image_standard">Visual & Asset Standard</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Enforcement Severity *</label>
                  <select
                    value={newRuleForm.severity}
                    onChange={(e) => setNewRuleForm({ ...newRuleForm, severity: e.target.value })}
                    className="select"
                  >
                    <option value="critical">Critical (Hard Block)</option>
                    <option value="high">High (Strict Flag)</option>
                    <option value="warning">Warning / Medium</option>
                    <option value="low">Low (Advisory)</option>
                  </select>
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: 12 }}>
                <label className="form-label">Trigger Pattern or Forbidden Text *</label>
                <input
                  type="text"
                  value={newRuleForm.pattern}
                  onChange={(e) => setNewRuleForm({ ...newRuleForm, pattern: e.target.value })}
                  placeholder="e.g. 100% secure, unhackable, zero risk"
                  className="input"
                  required
                />
                <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: 2 }}>
                  Content containing this phrase will trigger a governance violation.
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: 12 }}>
                <label className="form-label">Requirement & Explanation *</label>
                <textarea
                  value={newRuleForm.explanation}
                  onChange={(e) => setNewRuleForm({ ...newRuleForm, explanation: e.target.value })}
                  placeholder="Explain why this rule exists and how creators should write compliant content..."
                  className="input"
                  rows={3}
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12, marginBottom: 12 }}>
                <div className="form-group">
                  <label className="form-label">Link to Source Document</label>
                  <select
                    value={newRuleForm.source_id}
                    onChange={(e) => setNewRuleForm({ ...newRuleForm, source_id: e.target.value })}
                    className="select"
                  >
                    <option value="">None / General Guideline</option>
                    {sources.map(s => (
                      <option key={s.id} value={s.id}>
                        {s.title} ({s.filename})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Page Number</label>
                  <input
                    type="number"
                    min="1"
                    value={newRuleForm.page_number}
                    onChange={(e) => setNewRuleForm({ ...newRuleForm, page_number: e.target.value })}
                    placeholder="e.g. 4"
                    className="input"
                  />
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: 16 }}>
                <label className="form-label">Supporting Evidence Passage</label>
                <textarea
                  value={newRuleForm.evidence_passage}
                  onChange={(e) => setNewRuleForm({ ...newRuleForm, evidence_passage: e.target.value })}
                  placeholder="Quotation from the brand guidelines supporting this requirement..."
                  className="input"
                  rows={2}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button
                  type="button"
                  onClick={() => setAddRuleModalOpen(false)}
                  className="btn btn-secondary"
                  disabled={savingNewRule}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingNewRule}
                  className="btn btn-primary"
                >
                  {savingNewRule ? 'Creating...' : 'Create Rule (Pending Review)'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Document Text Viewing Modal */}
      {viewTextModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 110,
          padding: 20
        }}>
          <div className="card" style={{ width: '100%', maxWidth: 780, maxHeight: '90vh', display: 'flex', flexDirection: 'column', background: '#131b2e', border: '1px solid rgba(99, 102, 241, 0.4)' }}>
            <div className="flex-between" style={{ marginBottom: 12 }}>
              <div>
                <h2 className="title-md" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <FileText size={18} color="#818cf8" />
                  {viewTextData ? viewTextData.filename : 'Document Text'}
                </h2>
                {viewTextData && (
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: 2 }}>
                    {viewTextData.total_pages} page(s) | {viewTextData.total_characters} characters extracted locally
                  </div>
                )}
              </div>
              <button
                onClick={() => setViewTextModalOpen(false)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4 }}
              >
                <X size={18} />
              </button>
            </div>

            {loadingText ? (
              <div style={{ padding: 40, textAlign: 'center', color: '#a5b4fc' }}>
                <RefreshCw size={24} className="spin" style={{ margin: '0 auto 12px' }} />
                Extracting document text from storage...
              </div>
            ) : viewTextData ? (
              <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
                {/* Page Selector Tabs */}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10, paddingBottom: 8, borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                  <button
                    onClick={() => setSelectedTextPage(0)}
                    className={`tab-btn ${selectedTextPage === 0 ? 'active' : ''}`}
                    style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                  >
                    All Pages ({viewTextData.total_pages})
                  </button>
                  {viewTextData.pages.map((p: any) => (
                    <button
                      key={p.page_number}
                      onClick={() => setSelectedTextPage(p.page_number)}
                      className={`tab-btn ${selectedTextPage === p.page_number ? 'active' : ''}`}
                      style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                    >
                      Page {p.page_number}
                    </button>
                  ))}
                </div>

                {/* Text View Box */}
                <div style={{
                  flex: 1,
                  minHeight: 280,
                  maxHeight: 460,
                  overflowY: 'auto',
                  background: '#0a0e1a',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 6,
                  padding: 14,
                  fontSize: '0.8rem',
                  lineHeight: 1.6,
                  color: '#e2e8f0',
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace'
                }}>
                  {selectedTextPage === 0
                    ? viewTextData.full_text || '[No extractable text]'
                    : (viewTextData.pages.find((p: any) => p.page_number === selectedTextPage)?.text || '[No text on this page]')}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 14 }}>
                  <button
                    onClick={() => {
                      setViewTextModalOpen(false);
                      handleOpenAddRule();
                    }}
                    className="btn btn-secondary"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.8rem' }}
                  >
                    <Plus size={14} />
                    Add Rule from this Document
                  </button>
                  <button
                    onClick={() => setViewTextModalOpen(false)}
                    className="btn btn-primary"
                    style={{ fontSize: '0.8rem' }}
                  >
                    Close
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ padding: 40, textAlign: 'center', color: '#fb7185' }}>
                Failed to load document text.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
