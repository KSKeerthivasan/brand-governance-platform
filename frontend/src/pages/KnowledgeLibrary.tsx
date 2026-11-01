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
  Plus,
  FileSpreadsheet
} from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { StatusBadge } from '../components/StatusBadge';
import { KnowledgeRule, KnowledgeFact, KnowledgeSource, BrandAsset, Brand } from '../types';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import { ExcelImportModal } from '../components/ExcelImportModal';
import { BrandProfileModal } from '../components/BrandProfileModal';

export const KnowledgeLibrary: React.FC = () => {
  const { role } = useAuth();
  const [searchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const initialTab = (tabParam && ['rules', 'facts', 'assets', 'sources', 'rescore'].includes(tabParam))
    ? (tabParam as 'rules' | 'facts' | 'assets' | 'sources' | 'rescore')
    : 'rules';

  const [activeTab, setActiveTab] = useState<'rules' | 'facts' | 'assets' | 'sources' | 'rescore'>(initialTab);

  useEffect(() => {
    if (tabParam && ['rules', 'facts', 'assets', 'sources', 'rescore'].includes(tabParam)) {
      setActiveTab(tabParam as 'rules' | 'facts' | 'assets' | 'sources' | 'rescore');
    }
  }, [tabParam]);

  const [rules, setRules] = useState<KnowledgeRule[]>([]);
  const [facts, setFacts] = useState<KnowledgeFact[]>([]);
  const [assets, setAssets] = useState<BrandAsset[]>([]);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [rescoreJobs, setRescoreJobs] = useState<any[]>([]);
  const [kbVersions, setKbVersions] = useState<any[]>([]);
  const [selectedRescoreJob, setSelectedRescoreJob] = useState<any | null>(null);
  const [rescoringTriggering, setRescoringTriggering] = useState(false);
  const [selectedKbVersionId, setSelectedKbVersionId] = useState<string>('');
  const [loading, setLoading] = useState(true);

  // Canonical Brand Asset & Document Upload State
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [uploading, setUploading] = useState(false);

  // Asset upload modal state
  const [assetModalOpen, setAssetModalOpen] = useState(false);
  const [assetFile, setAssetFile] = useState<File | null>(null);
  const [assetTitle, setAssetTitle] = useState('');

  // Reference document upload modal state
  const [sourceModalOpen, setSourceModalOpen] = useState(false);
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [sourceTitle, setSourceTitle] = useState('');
  const [sourceType, setSourceType] = useState('pdf_brand_guidelines');

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

  // Round 3 Staged Excel & Brand Profile Modals
  const [excelModalOpen, setExcelModalOpen] = useState(false);
  const [brandProfileModalOpen, setBrandProfileModalOpen] = useState(false);
  const [activating, setActivating] = useState(false);

  const handleActivateKnowledgeBase = async () => {
    const reason = prompt("Enter activation reason for new immutable manifest snapshot:", "Published new approved guidelines & catalogue baseline");
    if (reason === null) return;
    setActivating(true);
    try {
      const res = await api.activateKnowledgeBase(reason);
      alert(`Knowledge Base Version ${res.version_num} activated successfully!\nSHA-256 Manifest: ${res.manifest_sha256.substring(0, 16)}...\nProducts: ${res.counts.products}, Claims: ${res.counts.claims}, Disclosures: ${res.counts.required_disclosures}`);
      await loadData();
    } catch (err: any) {
      alert(`Activation error: ${err.message}`);
    } finally {
      setActivating(false);
    }
  };

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
      const [r, f, a, s, b, rJobs, versions] = await Promise.all([
        api.getRules(),
        api.getFacts(),
        api.getAssets(),
        api.getKnowledgeSources(),
        api.getBrands(),
        api.getRescoreJobs().catch(() => []),
        api.getKnowledgeBaseVersions().catch(() => [])
      ]);
      setRules(r);
      setFacts(f);
      setAssets(a);
      setSources(s);
      setBrands(b);
      setRescoreJobs(rJobs || []);
      setKbVersions(versions || []);
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

  const handleUploadAsset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assetFile) {
      alert("Please select an image file (PNG, SVG, JPG, WEBP).");
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', assetFile);
      formData.append('title', assetTitle.trim() || assetFile.name);
      formData.append('source_type', 'brand_asset_image');
      if (selectedBrandId) formData.append('brand_id', selectedBrandId);

      await api.uploadKnowledge(formData);
      setAssetModalOpen(false);
      setAssetFile(null);
      setAssetTitle('');
      await loadData();
    } catch (err: any) {
      alert(`Asset upload error: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleUploadSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceFile) {
      alert("Please select a PDF document.");
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', sourceFile);
      formData.append('title', sourceTitle.trim() || sourceFile.name);
      formData.append('source_type', sourceType);
      if (selectedBrandId) formData.append('brand_id', selectedBrandId);

      const created = await api.uploadKnowledge(formData);
      setSourceModalOpen(false);
      setSourceFile(null);
      setSourceTitle('');
      alert(`Uploaded '${created.title}'. Extracted ${created.rules_count || 0} candidate rules and ${created.facts_count || 0} facts into Pending Review.`);
      await loadData();
    } catch (err: any) {
      alert(`Document upload error: ${err.message}`);
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

  const handleTriggerRescore = async () => {
    setRescoringTriggering(true);
    try {
      const res = await api.triggerRescoreJob({
        knowledge_base_version_id: selectedKbVersionId || undefined
      });
      alert(`Simulation job launched successfully!\nEvaluated ${res.completed_items || res.total_items} historical assets against Version ${res.version_num}.\nAudit trails and historical manifests remain 100% immutable.`);
      await loadData(true);
      if (res.job_id) {
        const fullJob = await api.getRescoreJob(res.job_id);
        setSelectedRescoreJob(fullJob);
      }
    } catch (err: any) {
      alert(`Simulation error: ${err.message}`);
    } finally {
      setRescoringTriggering(false);
    }
  };

  const handleSelectRescoreJob = async (jobId: string) => {
    try {
      const fullJob = await api.getRescoreJob(jobId);
      setSelectedRescoreJob(fullJob);
    } catch (err: any) {
      alert(`Error fetching job details: ${err.message}`);
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
            onClick={() => setBrandProfileModalOpen(true)}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.82rem' }}
          >
            <BookOpen size={15} color="#818cf8" />
            Brand Profile Form
          </button>
          <button
            onClick={() => setExcelModalOpen(true)}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.82rem' }}
          >
            <FileSpreadsheet size={15} color="#34d399" />
            Import Excel
          </button>
          <button
            onClick={handleActivateKnowledgeBase}
            disabled={activating}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.82rem', borderColor: 'rgba(99, 102, 241, 0.4)' }}
          >
            <ShieldCheck size={15} color="#60a5fa" />
            {activating ? 'Activating...' : 'Activate Version'}
          </button>
        </div>
      </div>

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
          <button
            onClick={() => setActiveTab('rescore')}
            className={`tab-btn ${activeTab === 'rescore' ? 'active' : ''}`}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <RefreshCw size={13} />
            Impact Rescoring Hub
            {rescoreJobs.length > 0 && (
              <span style={{ fontSize: '0.68rem', padding: '1px 6px', borderRadius: 999, background: 'rgba(99, 102, 241, 0.25)', color: '#a5b4fc', border: '1px solid rgba(99, 102, 241, 0.4)' }}>
                {rescoreJobs.length}
              </span>
            )}
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="flex-between" style={{ alignItems: 'center', marginBottom: 4 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff' }}>Brand Asset Library</h3>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                Official brand logos, product photography, and approved reference creatives used for visual governance checks.
              </p>
            </div>
            {isReviewer && (
              <button
                onClick={() => {
                  setAssetFile(null);
                  setAssetTitle('');
                  setAssetModalOpen(true);
                }}
                className="btn btn-primary"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.82rem' }}
              >
                <Upload size={14} /> Upload Brand Asset
              </button>
            )}
          </div>

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
        </div>
      )}

      {/* Tab 4: Uploaded Sources */}
      {activeTab === 'sources' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="flex-between" style={{ alignItems: 'center', marginBottom: 4 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff' }}>Reference Documents & Uploaded Sources</h3>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                Optional PDF brand guideline manuals, product specifications, and reference materials. Structured forms remain authoritative.
              </p>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={handleViewSamplePdf}
                className="btn btn-secondary"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.82rem' }}
                title="View sample brand guidelines reference PDF"
              >
                <Download size={14} /> View Sample Reference (PDF)
              </button>
              {isReviewer && (
                <button
                  onClick={() => {
                    setSourceFile(null);
                    setSourceTitle('');
                    setSourceType('pdf_brand_guidelines');
                    setSourceModalOpen(true);
                  }}
                  className="btn btn-primary"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.82rem' }}
                >
                  <Upload size={14} /> Upload Reference Document
                </button>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {sources.length === 0 ? (
              <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-dim)' }}>
                No reference documents uploaded yet. Use the "Upload Reference Document" button above to add PDF guidelines.
              </div>
            ) : (
              sources.map((src) => (
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
              ))
            )}
          </div>
        </div>
      )}

      {activeTab === 'rescore' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Simulation Header Banner */}
          <div className="card" style={{
            background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%)',
            border: '1px solid rgba(99, 102, 241, 0.35)',
            position: 'relative',
            overflow: 'hidden'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '4px 10px',
                    borderRadius: 999,
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    background: 'rgba(99, 102, 241, 0.2)',
                    color: '#a5b4fc',
                    border: '1px solid rgba(99, 102, 241, 0.4)'
                  }}>
                    <ShieldCheck size={13} /> Non-Destructive Impact Simulation
                  </span>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '4px 10px',
                    borderRadius: 999,
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    background: 'rgba(16, 185, 129, 0.15)',
                    color: '#34d399',
                    border: '1px solid rgba(16, 185, 129, 0.3)'
                  }}>
                    <CheckCircle size={13} /> 100% Immutable Historical Manifests
                  </span>
                </div>
                <h2 className="title-md" style={{ color: '#f8fafc', fontSize: '1.25rem', marginBottom: 6 }}>
                  Historical Knowledge Policy Rescoring Hub
                </h2>
                <p style={{ color: '#94a3b8', fontSize: '0.85rem', maxWidth: 700, margin: 0, lineHeight: 1.5 }}>
                  Evaluate and measure the direct impact of activating new brand guidelines, product catalogue variants, or claim updates across your entire historical ad catalog. Original governance runs and baseline audit trails remain permanently untouched.
                </p>
              </div>

              {isReviewer && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <select
                    value={selectedKbVersionId}
                    onChange={(e) => setSelectedKbVersionId(e.target.value)}
                    className="input"
                    style={{ minWidth: 200, fontSize: '0.82rem', padding: '8px 12px' }}
                  >
                    <option value="">Active Version (Default)</option>
                    {kbVersions.map((v: any) => (
                      <option key={v.id} value={v.id}>
                        Version {v.version_num} ({v.version_tag || 'Standard'}) {v.is_active ? '— Active' : ''}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={handleTriggerRescore}
                    disabled={rescoringTriggering}
                    className="btn btn-primary"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '9px 16px',
                      background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                      boxShadow: '0 4px 14px rgba(99, 102, 241, 0.4)'
                    }}
                  >
                    <RefreshCw size={15} className={rescoringTriggering ? 'spin' : ''} />
                    {rescoringTriggering ? 'Evaluating Catalog...' : 'Simulate Policy Rescore'}
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Past Simulation Batches */}
          {rescoreJobs.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '48px 24px', border: '1px dashed var(--border-subtle)' }}>
              <RefreshCw size={36} color="#6366f1" style={{ margin: '0 auto 16px', opacity: 0.6 }} />
              <h3 style={{ fontSize: '1.05rem', color: '#f8fafc', marginBottom: 8 }}>No Rescoring Simulations Yet</h3>
              <p style={{ fontSize: '0.85rem', color: '#94a3b8', maxWidth: 480, margin: '0 auto 20px' }}>
                Trigger a simulation above to evaluate your historical content assets against the newly activated brand knowledge manifest.
              </p>
              {isReviewer && (
                <button
                  onClick={handleTriggerRescore}
                  disabled={rescoringTriggering}
                  className="btn btn-secondary"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
                >
                  <RefreshCw size={14} /> Run First Simulation
                </button>
              )}
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: selectedRescoreJob ? '340px 1fr' : '1fr', gap: 20 }}>
              {/* Jobs List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Simulation Runs ({rescoreJobs.length})
                </div>
                {rescoreJobs.map((job: any) => {
                  const isSelected = selectedRescoreJob?.id === job.id;
                  return (
                    <div
                      key={job.id}
                      onClick={() => handleSelectRescoreJob(job.id)}
                      className="card hover-glow"
                      style={{
                        cursor: 'pointer',
                        padding: 16,
                        border: isSelected ? '1px solid #6366f1' : '1px solid var(--border-subtle)',
                        background: isSelected ? 'rgba(99, 102, 241, 0.12)' : 'var(--card-bg)',
                        transition: 'all 0.2s ease'
                      }}
                    >
                      <div className="flex-between" style={{ marginBottom: 6 }}>
                        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>
                          Target Version {job.version_num || 'Active'}
                        </span>
                        <span style={{
                          fontSize: '0.7rem',
                          padding: '2px 8px',
                          borderRadius: 999,
                          fontWeight: 600,
                          background: job.status === 'completed' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(234, 179, 8, 0.2)',
                          color: job.status === 'completed' ? '#34d399' : '#facc15'
                        }}>
                          {job.status}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', justifyContent: 'space-between' }}>
                        <span>Assets evaluated: {job.completed_items || job.total_items}</span>
                        <span>{new Date(job.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Selected Job Detail View */}
              {selectedRescoreJob && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                  {/* Job Metrics Summary */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                    <div className="card" style={{ padding: 14, textAlign: 'center' }}>
                      <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>Assets Evaluated</div>
                      <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f8fafc', marginTop: 4 }}>
                        {selectedRescoreJob.total_items || 0}
                      </div>
                    </div>
                    <div className="card" style={{ padding: 14, textAlign: 'center' }}>
                      <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>Regressed (New Issues)</div>
                      <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f87171', marginTop: 4 }}>
                        {selectedRescoreJob.items?.filter((it: any) =>
                          (it.status_before === 'approved' && it.status_after !== 'approved') ||
                          (it.overall_score_after < it.overall_score_before)
                        ).length || 0}
                      </div>
                    </div>
                    <div className="card" style={{ padding: 14, textAlign: 'center' }}>
                      <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>Improved / Compliant</div>
                      <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#34d399', marginTop: 4 }}>
                        {selectedRescoreJob.items?.filter((it: any) =>
                          (it.status_before !== 'approved' && it.status_after === 'approved') ||
                          (it.overall_score_after > it.overall_score_before)
                        ).length || 0}
                      </div>
                    </div>
                    <div className="card" style={{ padding: 14, textAlign: 'center' }}>
                      <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>Unaffected / Neutral</div>
                      <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#94a3b8', marginTop: 4 }}>
                        {selectedRescoreJob.items?.filter((it: any) =>
                          it.overall_score_after === it.overall_score_before && it.status_before === it.status_after
                        ).length || 0}
                      </div>
                    </div>
                  </div>

                  {/* Rescore Batch Items Table */}
                  <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                    <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h3 style={{ fontSize: '0.92rem', fontWeight: 600, color: '#f8fafc', margin: 0 }}>
                        Catalog Impact Analysis ({selectedRescoreJob.items?.length || 0} assets)
                      </h3>
                      <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                        Version {selectedRescoreJob.version_num} Simulation
                      </span>
                    </div>

                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                        <thead>
                          <tr style={{ background: 'rgba(15, 23, 42, 0.6)', borderBottom: '1px solid var(--border-subtle)', textAlign: 'left', color: '#94a3b8' }}>
                            <th style={{ padding: '10px 16px' }}>Content Item</th>
                            <th style={{ padding: '10px 16px' }}>Prior Baseline</th>
                            <th style={{ padding: '10px 16px' }}>Rescored Impact</th>
                            <th style={{ padding: '10px 16px' }}>Findings Shift</th>
                            <th style={{ padding: '10px 16px' }}>Transition Verdict</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(!selectedRescoreJob.items || selectedRescoreJob.items.length === 0) ? (
                            <tr>
                              <td colSpan={5} style={{ padding: 24, textAlign: 'center', color: '#94a3b8' }}>
                                No evaluated item details available.
                              </td>
                            </tr>
                          ) : (
                            selectedRescoreJob.items.map((item: any) => {
                              const isRegressed =
                                (item.status_before === 'approved' && item.status_after !== 'approved') ||
                                (item.overall_score_after < item.overall_score_before);
                              const isImproved =
                                (item.status_before !== 'approved' && item.status_after === 'approved') ||
                                (item.overall_score_after > item.overall_score_before);

                              return (
                                <tr key={item.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                  <td style={{ padding: '12px 16px', fontWeight: 500, color: '#f8fafc' }}>
                                    <div>{item.content_item_title || 'Historical Asset'}</div>
                                    <div style={{ fontSize: '0.72rem', color: '#64748b' }}>
                                      Version {item.content_version_num || 1} • {item.content_item_channel || 'all'}
                                    </div>
                                  </td>
                                  <td style={{ padding: '12px 16px' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                      <span style={{
                                        fontSize: '0.72rem',
                                        padding: '2px 8px',
                                        borderRadius: 4,
                                        fontWeight: 600,
                                        background: item.status_before === 'approved' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                                        color: item.status_before === 'approved' ? '#34d399' : '#f87171'
                                      }}>
                                        {item.status_before || 'unscored'}
                                      </span>
                                      <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>
                                        {item.overall_score_before != null ? `${item.overall_score_before}%` : '—'}
                                      </span>
                                    </div>
                                  </td>
                                  <td style={{ padding: '12px 16px' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                      <span style={{
                                        fontSize: '0.72rem',
                                        padding: '2px 8px',
                                        borderRadius: 4,
                                        fontWeight: 600,
                                        background: item.status_after === 'approved' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                                        color: item.status_after === 'approved' ? '#34d399' : '#f87171'
                                      }}>
                                        {item.status_after || 'unscored'}
                                      </span>
                                      <span style={{ color: '#f8fafc', fontWeight: 600, fontSize: '0.8rem' }}>
                                        {item.overall_score_after != null ? `${item.overall_score_after}%` : '—'}
                                      </span>
                                    </div>
                                  </td>
                                  <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: '0.76rem' }}>
                                    {item.critical_findings_diff > 0 && (
                                      <div style={{ color: '#f87171' }}>+{item.critical_findings_diff} Critical</div>
                                    )}
                                    {item.major_findings_diff > 0 && (
                                      <div style={{ color: '#fb923c' }}>+{item.major_findings_diff} Major</div>
                                    )}
                                    {item.critical_findings_diff <= 0 && item.major_findings_diff <= 0 && (
                                      <span style={{ color: '#64748b' }}>No new violations</span>
                                    )}
                                  </td>
                                  <td style={{ padding: '12px 16px' }}>
                                    {isRegressed ? (
                                      <span style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: 4,
                                        fontSize: '0.72rem',
                                        fontWeight: 600,
                                        padding: '3px 8px',
                                        borderRadius: 999,
                                        background: 'rgba(239, 68, 68, 0.15)',
                                        color: '#f87171',
                                        border: '1px solid rgba(239, 68, 68, 0.3)'
                                      }}>
                                        <AlertTriangle size={12} /> Regressed
                                      </span>
                                    ) : isImproved ? (
                                      <span style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: 4,
                                        fontSize: '0.72rem',
                                        fontWeight: 600,
                                        padding: '3px 8px',
                                        borderRadius: 999,
                                        background: 'rgba(16, 185, 129, 0.15)',
                                        color: '#34d399',
                                        border: '1px solid rgba(16, 185, 129, 0.3)'
                                      }}>
                                        <CheckCircle size={12} /> Improved
                                      </span>
                                    ) : (
                                      <span style={{
                                        fontSize: '0.72rem',
                                        fontWeight: 500,
                                        padding: '3px 8px',
                                        borderRadius: 999,
                                        background: 'rgba(100, 116, 139, 0.15)',
                                        color: '#94a3b8'
                                      }}>
                                        Unaffected
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              );
                            })
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
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

      {/* Canonical Brand Asset Upload Modal */}
      {assetModalOpen && (
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
            maxWidth: 540,
            background: '#131b2e',
            border: '1px solid rgba(255,255,255,0.18)',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
          }}>
            <div className="flex-between" style={{ marginBottom: 16, borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: 12 }}>
              <div>
                <h2 className="title-md" style={{ display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
                  <ImageIcon size={20} color="#818cf8" />
                  Upload Brand Asset
                </h2>
                <p className="text-sub" style={{ fontSize: '0.78rem', marginTop: 4, marginBottom: 0 }}>
                  Upload official brand logos, product photography, or packaging references.
                </p>
              </div>
              <button
                onClick={() => setAssetModalOpen(false)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4 }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleUploadAsset}>
              <div className="form-group" style={{ marginBottom: 14 }}>
                <label className="form-label">Asset Name / Title *</label>
                <input
                  type="text"
                  placeholder="e.g. Primary Brand Logo"
                  value={assetTitle}
                  onChange={(e) => setAssetTitle(e.target.value)}
                  className="input"
                  required
                />
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

              <div className="form-group" style={{ marginBottom: 18 }}>
                <label className="form-label">Image File (SVG, PNG, JPG, WEBP) *</label>
                <input
                  type="file"
                  accept=".svg,image/png,image/jpeg,image/webp"
                  onChange={(e) => setAssetFile(e.target.files?.[0] || null)}
                  className="input"
                  disabled={uploading}
                  required
                />
                <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 4, display: 'block' }}>
                  Transparent PNG or SVG preferred for official brand logos.
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button
                  type="button"
                  onClick={() => setAssetModalOpen(false)}
                  className="btn btn-secondary"
                  disabled={uploading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading || !assetFile}
                  className="btn btn-primary"
                >
                  {uploading ? 'Uploading...' : 'Upload Asset'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Canonical Reference Document Upload Modal */}
      {sourceModalOpen && (
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
            maxWidth: 540,
            background: '#131b2e',
            border: '1px solid rgba(255,255,255,0.18)',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
          }}>
            <div className="flex-between" style={{ marginBottom: 16, borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: 12 }}>
              <div>
                <h2 className="title-md" style={{ display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
                  <FileText size={20} color="#818cf8" />
                  Upload Reference Document
                </h2>
                <p className="text-sub" style={{ fontSize: '0.78rem', marginTop: 4, marginBottom: 0 }}>
                  Upload optional brand guidelines manuals or supporting reference documents in PDF format.
                </p>
              </div>
              <button
                onClick={() => setSourceModalOpen(false)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4 }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleUploadSource}>
              <div className="form-group" style={{ marginBottom: 14 }}>
                <label className="form-label">Document Title *</label>
                <input
                  type="text"
                  placeholder="e.g. Brand Guidelines Reference Manual"
                  value={sourceTitle}
                  onChange={(e) => setSourceTitle(e.target.value)}
                  className="input"
                  required
                />
              </div>

              <div className="form-group" style={{ marginBottom: 14 }}>
                <label className="form-label">Document Category</label>
                <select
                  value={sourceType}
                  onChange={(e) => setSourceType(e.target.value)}
                  className="select"
                  disabled={uploading}
                >
                  <option value="pdf_brand_guidelines">PDF Brand Guidelines</option>
                  <option value="pdf_product_knowledge">PDF Product Knowledge & Specs</option>
                  <option value="supporting_doc">Supporting Evidence Document</option>
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

              <div className="form-group" style={{ marginBottom: 18 }}>
                <label className="form-label">PDF Document (.pdf) *</label>
                <input
                  type="file"
                  accept=".pdf,application/pdf"
                  onChange={(e) => setSourceFile(e.target.files?.[0] || null)}
                  className="input"
                  disabled={uploading}
                  required
                />
                <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 4, display: 'block' }}>
                  Extracted rules and facts will be placed into Pending Review.
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button
                  type="button"
                  onClick={() => setSourceModalOpen(false)}
                  className="btn btn-secondary"
                  disabled={uploading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading || !sourceFile}
                  className="btn btn-primary"
                >
                  {uploading ? 'Processing Extraction...' : 'Upload & Extract Candidates'}
                </button>
              </div>
            </form>
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

      {/* Round 3 Excel Import Modal */}
      <ExcelImportModal
        isOpen={excelModalOpen}
        onClose={() => setExcelModalOpen(false)}
        onSuccess={() => {
          setExcelModalOpen(false);
          loadData();
        }}
      />

      {/* Round 3 Brand Profile Modal */}
      <BrandProfileModal
        isOpen={brandProfileModalOpen}
        onClose={() => setBrandProfileModalOpen(false)}
        onSaved={() => {
          setBrandProfileModalOpen(false);
          loadData();
        }}
      />
    </div>
  );
};
