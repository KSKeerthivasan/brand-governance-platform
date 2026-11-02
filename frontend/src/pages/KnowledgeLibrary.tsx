import React, { useEffect, useState, useMemo } from 'react';
import {
  Upload,
  BookOpen,
  CheckCircle,
  XCircle,
  FileText,
  AlertCircle,
  Check,
  X,
  FileCheck,
  Shield,
  Tag,
  Edit3,
  RefreshCw,
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
  FileSpreadsheet,
  Star,
  Trash2,
  Eye,
  Search,
  Calendar,
  Package,
  Layers,
  SlidersHorizontal,
  CheckSquare,
  Clock
} from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { StatusBadge } from '../components/StatusBadge';
import {
  KnowledgeSource,
  BrandAsset,
  Brand,
  ProductItem,
  ClaimItem,
  RequiredDisclosureItem,
  StagedImportHistoryItem
} from '../types';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import { ExcelImportModal } from '../components/ExcelImportModal';
import { BrandProfileModal } from '../components/BrandProfileModal';

export const KnowledgeLibrary: React.FC = () => {
  const { role } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  // Exactly three primary tabs as mandated:
  // 1. 'facts' (Product Facts & Claims - default)
  // 2. 'assets' (Brand Assets)
  // 3. 'sources' (Uploaded Sources)
  const tabParam = searchParams.get('tab');
  const validTabs: Array<'facts' | 'assets' | 'sources'> = ['facts', 'assets', 'sources'];
  const initialTab = (tabParam && validTabs.includes(tabParam as any))
    ? (tabParam as 'facts' | 'assets' | 'sources')
    : 'facts';

  const [activeTab, setActiveTab] = useState<'facts' | 'assets' | 'sources'>(initialTab);

  // Sub-tabs inside Product Facts & Claims
  const [factsSubTab, setFactsSubTab] = useState<'products' | 'claims' | 'disclosures'>('products');

  useEffect(() => {
    if (tabParam && validTabs.includes(tabParam as any)) {
      setActiveTab(tabParam as 'facts' | 'assets' | 'sources');
    }
  }, [tabParam]);

  const handleTabChange = (newTab: 'facts' | 'assets' | 'sources') => {
    setActiveTab(newTab);
    setSearchParams({ tab: newTab });
  };

  // Live Data State
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [claims, setClaims] = useState<ClaimItem[]>([]);
  const [disclosures, setDisclosures] = useState<RequiredDisclosureItem[]>([]);
  const [assets, setAssets] = useState<BrandAsset[]>([]);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [stagedImports, setStagedImports] = useState<StagedImportHistoryItem[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [kbVersions, setKbVersions] = useState<any[]>([]);
  const [rescoreJobs, setRescoreJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Search & Filter State
  const [productSearch, setProductSearch] = useState('');
  const [productStatusFilter, setProductStatusFilter] = useState('all');
  const [claimSearch, setClaimSearch] = useState('');
  const [claimStatusFilter, setClaimStatusFilter] = useState('all');
  const [claimTypeFilter, setClaimTypeFilter] = useState('all');
  const [disclosureSearch, setDisclosureSearch] = useState('');
  const [assetCategoryFilter, setAssetCategoryFilter] = useState('all');
  const [assetStatusFilter, setAssetStatusFilter] = useState('all');

  // Detail Modals State
  const [selectedProduct, setSelectedProduct] = useState<ProductItem | null>(null);
  const [selectedClaim, setSelectedClaim] = useState<ClaimItem | null>(null);
  const [selectedDisclosure, setSelectedDisclosure] = useState<RequiredDisclosureItem | null>(null);

  // Brand Asset Upload Modal State
  const [assetModalOpen, setAssetModalOpen] = useState(false);
  const [assetFile, setAssetFile] = useState<File | null>(null);
  const [assetTitle, setAssetTitle] = useState('');
  const [assetCategory, setAssetCategory] = useState<'logo' | 'product_image' | 'brand_graphic' | 'approved_asset'>('logo');
  const [assetUsageNotes, setAssetUsageNotes] = useState('');
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [uploadingAsset, setUploadingAsset] = useState(false);

  // Reference Document Upload Modal State (Uploaded Sources tab)
  const [sourceModalOpen, setSourceModalOpen] = useState(false);
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [sourceTitle, setSourceTitle] = useState('');
  const [sourceType, setSourceType] = useState('pdf_brand_guidelines');
  const [uploadingSource, setUploadingSource] = useState(false);

  // Extracted PDF text viewing modal state
  const [viewTextModalOpen, setViewTextModalOpen] = useState(false);
  const [viewTextData, setViewTextData] = useState<any>(null);
  const [loadingText, setLoadingText] = useState(false);
  const [selectedTextPage, setSelectedTextPage] = useState<number>(1);
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);

  // Mandatory Top Controls Modals
  const [excelModalOpen, setExcelModalOpen] = useState(false);
  const [brandProfileModalOpen, setBrandProfileModalOpen] = useState(false);
  const [activating, setActivating] = useState(false);

  // Relocated Policy Impact Rescoring Modal
  const [rescoreModalOpen, setRescoreModalOpen] = useState(false);
  const [selectedKbVersionId, setSelectedKbVersionId] = useState<string>('');
  const [rescoringTriggering, setRescoringTriggering] = useState(false);
  const [selectedRescoreJob, setSelectedRescoreJob] = useState<any | null>(null);

  const isReviewer = role === 'knowledge_reviewer' || role === 'org_admin';

  // Load all live knowledge data
  const loadData = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const [prods, clms, discs, asts, srcs, imps, brnds, vers, rJobs] = await Promise.all([
        api.getProducts().catch(() => []),
        api.getClaims().catch(() => []),
        api.getDisclosures().catch(() => []),
        api.getAssets().catch(() => []),
        api.getKnowledgeSources().catch(() => []),
        api.getStagedImports().catch(() => []),
        api.getBrands().catch(() => []),
        api.getKnowledgeBaseVersions().catch(() => []),
        api.getRescoreJobs().catch(() => [])
      ]);

      setProducts(prods || []);
      setClaims(clms || []);
      setDisclosures(discs || []);
      setAssets(asts || []);
      setSources(srcs || []);
      setStagedImports(imps || []);
      setBrands(brnds || []);
      setKbVersions(vers || []);
      setRescoreJobs(rJobs || []);

      if (brnds.length > 0 && !selectedBrandId) {
        setSelectedBrandId(brnds[0].id);
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
    if (!uploadingAsset && !uploadingSource && !assetModalOpen && !sourceModalOpen && !reprocessingId) {
      loadData(true);
    }
  }, { intervalMs: 10000 });

  // 1. Mandatory Activation Handler
  const handleActivateKnowledgeBase = async () => {
    const reason = prompt(
      "Enter activation reason for new immutable manifest snapshot:",
      "Published new approved guidelines, catalogue & brand assets baseline"
    );
    if (reason === null) return;
    setActivating(true);
    try {
      const res = await api.activateKnowledgeBase(reason);
      alert(
        `Knowledge Base Version ${res.version_num} activated successfully!\n\n` +
        `SHA-256 Manifest: ${res.manifest_sha256.substring(0, 16)}...\n` +
        `Products: ${res.counts.products}, Claims: ${res.counts.claims}, Disclosures: ${res.counts.required_disclosures}`
      );
      await loadData();
    } catch (err: any) {
      alert(`Activation error: ${err.message}`);
    } finally {
      setActivating(false);
    }
  };

  // Brand Asset Upload Handler
  const handleUploadAsset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assetFile) {
      alert("Please select an image file (PNG, SVG, JPG, WEBP).");
      return;
    }
    setUploadingAsset(true);
    try {
      const formData = new FormData();
      formData.append('file', assetFile);
      formData.append('title', assetTitle.trim() || assetFile.name);
      formData.append('source_type', 'brand_asset_image');
      formData.append('asset_type', assetCategory);
      if (assetUsageNotes.trim()) {
        formData.append('usage_notes', assetUsageNotes.trim());
      }
      if (selectedBrandId) {
        formData.append('brand_id', selectedBrandId);
      }

      await api.uploadKnowledge(formData);
      setAssetModalOpen(false);
      setAssetFile(null);
      setAssetTitle('');
      setAssetUsageNotes('');
      setAssetCategory('logo');
      await loadData();
    } catch (err: any) {
      alert(`Asset upload error: ${err.message}`);
    } finally {
      setUploadingAsset(false);
    }
  };

  // Asset Approval / Review Handler
  const handleReviewAsset = async (assetId: string, status: 'approved' | 'rejected') => {
    try {
      await api.reviewAsset(assetId, status);
      await loadData();
    } catch (err: any) {
      alert(`Review error: ${err.message}`);
    }
  };

  // Asset Deletion Handler
  const handleDeleteAsset = async (assetId: string) => {
    if (!confirm("Are you sure you want to delete this brand asset?")) return;
    try {
      await api.deleteAsset(assetId);
      await loadData();
    } catch (err: any) {
      alert(`Delete error: ${err.message}`);
    }
  };

  // Reference Source Upload Handler
  const handleUploadSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceFile) {
      alert("Please select a document file.");
      return;
    }
    setUploadingSource(true);
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
      alert(`Uploaded '${created.title}'. Stored in Pending Review.`);
      await loadData();
    } catch (err: any) {
      alert(`Document upload error: ${err.message}`);
    } finally {
      setUploadingSource(false);
    }
  };

  // View PDF Extracted Text Handler
  const handleOpenViewText = async (sourceId: string) => {
    setLoadingText(true);
    setViewTextModalOpen(true);
    setSelectedTextPage(1);
    try {
      const data = await api.getSourceText(sourceId);
      setViewTextData(data);
    } catch (err: any) {
      alert(`Could not load document text: ${err.message}`);
      setViewTextModalOpen(false);
    } finally {
      setLoadingText(false);
    }
  };

  // Reprocess PDF Source Document Handler
  const handleReprocessSource = async (sourceId: string) => {
    if (!confirm("Reprocess this document with Gemini? Existing approved knowledge will be preserved.")) return;
    setReprocessingId(sourceId);
    try {
      const updated = await api.reprocessSource(sourceId);
      alert(`Reprocessing complete for '${updated.title}'. Extracted rules: ${updated.rules_count}, facts: ${updated.facts_count}.`);
      await loadData();
    } catch (err: any) {
      alert(`Reprocessing error: ${err.message}`);
    } finally {
      setReprocessingId(null);
    }
  };

  // Policy Impact Hub Trigger Simulation Handler
  const handleTriggerRescore = async () => {
    setRescoringTriggering(true);
    try {
      const payload: any = {};
      if (selectedKbVersionId) {
        payload.knowledge_base_version_id = selectedKbVersionId;
      }
      const job = await api.triggerRescoreJob(payload);
      alert(`Policy Impact Simulation Job ${job.job_id} initiated! Processed ${job.total_items} historical ad items.`);
      await loadData();
      if (job && job.job_id) {
        setSelectedRescoreJob(job);
      }
    } catch (err: any) {
      alert(`Rescore simulation error: ${err.message}`);
    } finally {
      setRescoringTriggering(false);
    }
  };

  // Check Primary Logo Activation Readiness
  const approvedPrimaryLogo = useMemo(() => {
    return assets.find(
      (a) => (a.asset_type === 'logo' || a.asset_name.toLowerCase().includes('logo')) && a.status === 'approved'
    );
  }, [assets]);

  const anyLogo = useMemo(() => {
    return assets.find(
      (a) => a.asset_type === 'logo' || a.asset_name.toLowerCase().includes('logo')
    );
  }, [assets]);

  // Filtered Products
  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      const matchesSearch =
        productSearch === '' ||
        p.product_name.toLowerCase().includes(productSearch.toLowerCase()) ||
        p.product_id.toLowerCase().includes(productSearch.toLowerCase()) ||
        (p.sku && p.sku.toLowerCase().includes(productSearch.toLowerCase())) ||
        p.product_category.toLowerCase().includes(productSearch.toLowerCase());

      const matchesStatus =
        productStatusFilter === 'all' ||
        p.record_status.toLowerCase() === productStatusFilter.toLowerCase();

      return matchesSearch && matchesStatus;
    });
  }, [products, productSearch, productStatusFilter]);

  // Filtered Claims
  const filteredClaims = useMemo(() => {
    return claims.filter((c) => {
      const matchesSearch =
        claimSearch === '' ||
        c.claim_id.toLowerCase().includes(claimSearch.toLowerCase()) ||
        c.claim_text.toLowerCase().includes(claimSearch.toLowerCase()) ||
        c.applicable_product_id.toLowerCase().includes(claimSearch.toLowerCase()) ||
        c.applicable_market.toLowerCase().includes(claimSearch.toLowerCase());

      const matchesStatus =
        claimStatusFilter === 'all' ||
        c.claim_status.toLowerCase() === claimStatusFilter.toLowerCase();

      const matchesType =
        claimTypeFilter === 'all' ||
        c.claim_type.toLowerCase() === claimTypeFilter.toLowerCase();

      return matchesSearch && matchesStatus && matchesType;
    });
  }, [claims, claimSearch, claimStatusFilter, claimTypeFilter]);

  // Distinct Claim Types for filter
  const distinctClaimTypes = useMemo(() => {
    const types = new Set<string>();
    claims.forEach((c) => {
      if (c.claim_type) types.add(c.claim_type);
    });
    return Array.from(types).sort();
  }, [claims]);

  // Filtered Required Disclosures
  const filteredDisclosures = useMemo(() => {
    return disclosures.filter((d) => {
      return (
        disclosureSearch === '' ||
        d.disclosure_id.toLowerCase().includes(disclosureSearch.toLowerCase()) ||
        d.disclosure_text.toLowerCase().includes(disclosureSearch.toLowerCase()) ||
        d.applicable_product_id.toLowerCase().includes(disclosureSearch.toLowerCase()) ||
        d.applicable_market.toLowerCase().includes(disclosureSearch.toLowerCase()) ||
        d.applies_when.toLowerCase().includes(disclosureSearch.toLowerCase())
      );
    });
  }, [disclosures, disclosureSearch]);

  // Filtered Brand Assets
  const filteredAssets = useMemo(() => {
    return assets.filter((a) => {
      const isLogo = a.asset_type === 'logo' || a.asset_name.toLowerCase().includes('logo');
      const matchesCategory =
        assetCategoryFilter === 'all' ||
        (assetCategoryFilter === 'logo' && isLogo) ||
        (assetCategoryFilter === 'product_image' && a.asset_type === 'product_image') ||
        (assetCategoryFilter === 'brand_graphic' && a.asset_type === 'brand_graphic') ||
        (assetCategoryFilter === 'approved_asset' && !isLogo && a.asset_type !== 'product_image' && a.asset_type !== 'brand_graphic');

      const matchesStatus =
        assetStatusFilter === 'all' ||
        a.status.toLowerCase() === assetStatusFilter.toLowerCase();

      return matchesCategory && matchesStatus;
    });
  }, [assets, assetCategoryFilter, assetStatusFilter]);

  return (
    <div>
      {/* Top Header with Mandatory Controls Preserved */}
      <div className="flex-between" style={{ marginBottom: 20, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 className="title-xl">Knowledge Library & Brand Governance</h1>
          <p className="text-sub">
            Authoritative Product Catalogue, Claims Register, approved Brand Assets, and source documentation.
          </p>
        </div>

        {/* 1. Mandatory Top-Level Buttons (Preserved Exactly) */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
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

          {/* Relocated Policy Impact Hub Action */}
          <button
            onClick={() => setRescoreModalOpen(true)}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.82rem', borderColor: 'rgba(167, 139, 250, 0.4)' }}
          >
            <RefreshCw size={14} color="#c084fc" />
            Policy Impact Hub
            {rescoreJobs.length > 0 && (
              <span style={{ fontSize: '0.68rem', padding: '1px 6px', borderRadius: 999, background: 'rgba(167, 139, 250, 0.25)', color: '#e9d5ff' }}>
                {rescoreJobs.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* 2. Primary Tab Bar: EXACTLY THREE PRIMARY TABS */}
      <div style={{ borderBottom: '1px solid var(--border-subtle)', marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => handleTabChange('facts')}
            className={`tab-btn ${activeTab === 'facts' ? 'active' : ''}`}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            <Package size={15} />
            Product Facts & Claims ({products.length + claims.length + disclosures.length})
          </button>
          <button
            onClick={() => handleTabChange('assets')}
            className={`tab-btn ${activeTab === 'assets' ? 'active' : ''}`}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            <ImageIcon size={15} />
            Brand Assets ({assets.length})
          </button>
          <button
            onClick={() => handleTabChange('sources')}
            className={`tab-btn ${activeTab === 'sources' ? 'active' : ''}`}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            <FileText size={15} />
            Uploaded Sources ({sources.length + stagedImports.length})
          </button>
        </div>
      </div>

      {/* ===================================================================== */}
      {/* PRIMARY TAB 1: PRODUCT FACTS & CLAIMS (Default) */}
      {/* ===================================================================== */}
      {activeTab === 'facts' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Sub-Tab Navigation Bar */}
          <div className="flex-between" style={{ alignItems: 'center', background: 'rgba(15, 23, 42, 0.5)', padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                onClick={() => setFactsSubTab('products')}
                className={`btn ${factsSubTab === 'products' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '6px 14px', fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <Package size={14} />
                Products ({products.length})
              </button>
              <button
                onClick={() => setFactsSubTab('claims')}
                className={`btn ${factsSubTab === 'claims' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '6px 14px', fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <ShieldCheck size={14} />
                Claims ({claims.length})
              </button>
              <button
                onClick={() => setFactsSubTab('disclosures')}
                className={`btn ${factsSubTab === 'disclosures' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '6px 14px', fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <AlertCircle size={14} />
                Required Disclosures ({disclosures.length})
              </button>
            </div>

            <button
              onClick={() => setExcelModalOpen(true)}
              className="btn btn-secondary"
              style={{ fontSize: '0.78rem', padding: '5px 10px', display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <FileSpreadsheet size={13} color="#34d399" />
              Upload Updated Excel
            </button>
          </div>

          {/* SUB-TAB 1: PRODUCTS */}
          {factsSubTab === 'products' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* Filter controls */}
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ position: 'relative', flex: 1, minWidth: 240 }}>
                  <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
                  <input
                    type="text"
                    placeholder="Search products by name, product ID, SKU, or category..."
                    value={productSearch}
                    onChange={(e) => setProductSearch(e.target.value)}
                    className="input"
                    style={{ paddingLeft: 32, fontSize: '0.82rem' }}
                  />
                </div>
                <select
                  value={productStatusFilter}
                  onChange={(e) => setProductStatusFilter(e.target.value)}
                  className="input"
                  style={{ width: 160, fontSize: '0.82rem' }}
                >
                  <option value="all">All Statuses</option>
                  <option value="Active">Active</option>
                  <option value="Inactive">Inactive</option>
                  <option value="Discontinued">Discontinued</option>
                </select>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                  Showing {filteredProducts.length} of {products.length} products
                </span>
              </div>

              {/* Products Table */}
              <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
                    <thead>
                      <tr style={{ background: 'rgba(30, 41, 59, 0.7)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)' }}>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Product Name</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Product ID</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Category</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Offering Type</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>SKU / Variant</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Market</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Status</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredProducts.length === 0 ? (
                        <tr>
                          <td colSpan={8} style={{ padding: 36, textAlign: 'center', color: 'var(--text-dim)' }}>
                            <Package size={32} style={{ margin: '0 auto 8px', opacity: 0.5 }} />
                            <div>No products found matching the criteria.</div>
                            {products.length === 0 && (
                              <button
                                onClick={() => setExcelModalOpen(true)}
                                className="btn btn-secondary"
                                style={{ marginTop: 12, fontSize: '0.8rem' }}
                              >
                                <FileSpreadsheet size={14} style={{ marginRight: 6 }} /> Import Product Catalogue
                              </button>
                            )}
                          </td>
                        </tr>
                      ) : (
                        filteredProducts.map((p) => (
                          <tr
                            key={p.id}
                            style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)', transition: 'background 0.15s' }}
                            className="table-row-hover"
                          >
                            <td style={{ padding: '10px 14px', fontWeight: 600, color: '#f8fafc' }}>
                              {p.product_name}
                            </td>
                            <td style={{ padding: '10px 14px' }}>
                              <span style={{ fontFamily: 'monospace', background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: 4, color: '#93c5fd' }}>
                                {p.product_id}
                              </span>
                            </td>
                            <td style={{ padding: '10px 14px', color: 'var(--text-sub)' }}>
                              {p.product_category}
                            </td>
                            <td style={{ padding: '10px 14px', color: 'var(--text-sub)' }}>
                              {p.offering_type}
                            </td>
                            <td style={{ padding: '10px 14px', color: 'var(--text-dim)' }}>
                              {p.sku || p.variant_name || '—'}
                            </td>
                            <td style={{ padding: '10px 14px', color: 'var(--text-sub)' }}>
                              {p.applicable_market}
                            </td>
                            <td style={{ padding: '10px 14px' }}>
                              <span className={`badge ${p.record_status === 'Active' ? 'badge-success' : 'badge-neutral'}`}>
                                {p.record_status}
                              </span>
                            </td>
                            <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                              <button
                                onClick={() => setSelectedProduct(p)}
                                className="btn btn-secondary"
                                style={{ padding: '4px 10px', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                              >
                                <Eye size={12} /> View Details
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* SUB-TAB 2: CLAIMS */}
          {factsSubTab === 'claims' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* Filter controls */}
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ position: 'relative', flex: 1, minWidth: 240 }}>
                  <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
                  <input
                    type="text"
                    placeholder="Search claims by ID, claim text, or associated product..."
                    value={claimSearch}
                    onChange={(e) => setClaimSearch(e.target.value)}
                    className="input"
                    style={{ paddingLeft: 32, fontSize: '0.82rem' }}
                  />
                </div>
                <select
                  value={claimStatusFilter}
                  onChange={(e) => setClaimStatusFilter(e.target.value)}
                  className="input"
                  style={{ width: 160, fontSize: '0.82rem' }}
                >
                  <option value="all">All Statuses</option>
                  <option value="Approved">Approved</option>
                  <option value="Restricted">Restricted</option>
                  <option value="Prohibited">Prohibited</option>
                </select>
                <select
                  value={claimTypeFilter}
                  onChange={(e) => setClaimTypeFilter(e.target.value)}
                  className="input"
                  style={{ width: 160, fontSize: '0.82rem' }}
                >
                  <option value="all">All Types</option>
                  {distinctClaimTypes.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                  Showing {filteredClaims.length} of {claims.length} claims
                </span>
              </div>

              {/* Claims Table */}
              <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
                    <thead>
                      <tr style={{ background: 'rgba(30, 41, 59, 0.7)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)' }}>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Claim ID</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600, minWidth: 260 }}>Claim Text</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Type</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Status</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Associated Product</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Market</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Effective Dates</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredClaims.length === 0 ? (
                        <tr>
                          <td colSpan={8} style={{ padding: 36, textAlign: 'center', color: 'var(--text-dim)' }}>
                            <ShieldCheck size={32} style={{ margin: '0 auto 8px', opacity: 0.5 }} />
                            <div>No claims found matching the criteria.</div>
                            {claims.length === 0 && (
                              <button
                                onClick={() => setExcelModalOpen(true)}
                                className="btn btn-secondary"
                                style={{ marginTop: 12, fontSize: '0.8rem' }}
                              >
                                <FileSpreadsheet size={14} style={{ marginRight: 6 }} /> Import Claims Register
                              </button>
                            )}
                          </td>
                        </tr>
                      ) : (
                        filteredClaims.map((c) => {
                          const statusBadgeClass =
                            c.claim_status === 'Approved'
                              ? 'badge-success'
                              : c.claim_status === 'Restricted'
                              ? 'badge-warning'
                              : 'badge-danger';

                          return (
                            <tr
                              key={c.id}
                              style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}
                              className="table-row-hover"
                            >
                              <td style={{ padding: '10px 14px' }}>
                                <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#a5b4fc', background: 'rgba(99, 102, 241, 0.1)', padding: '2px 6px', borderRadius: 4 }}>
                                  {c.claim_id}
                                </span>
                              </td>
                              <td style={{ padding: '10px 14px', color: '#f8fafc', maxWidth: 360 }}>
                                <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {c.claim_text}
                                </div>
                              </td>
                              <td style={{ padding: '10px 14px' }}>
                                <span className="badge badge-neutral" style={{ fontSize: '0.72rem' }}>
                                  {c.claim_type}
                                </span>
                              </td>
                              <td style={{ padding: '10px 14px' }}>
                                <span className={`badge ${statusBadgeClass}`}>
                                  {c.claim_status}
                                </span>
                              </td>
                              <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: '0.78rem', color: '#93c5fd' }}>
                                {c.applicable_product_id}
                              </td>
                              <td style={{ padding: '10px 14px', color: 'var(--text-sub)' }}>
                                {c.applicable_market}
                              </td>
                              <td style={{ padding: '10px 14px', color: 'var(--text-dim)', fontSize: '0.75rem' }}>
                                {c.effective_from} → {c.effective_until || 'Indefinite'}
                              </td>
                              <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                                <button
                                  onClick={() => setSelectedClaim(c)}
                                  className="btn btn-secondary"
                                  style={{ padding: '4px 10px', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                                >
                                  <Eye size={12} /> View Details
                                </button>
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

          {/* SUB-TAB 3: REQUIRED DISCLOSURES */}
          {factsSubTab === 'disclosures' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* Filter controls */}
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ position: 'relative', flex: 1, minWidth: 240 }}>
                  <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
                  <input
                    type="text"
                    placeholder="Search disclosures by ID, text, applies when, or market..."
                    value={disclosureSearch}
                    onChange={(e) => setDisclosureSearch(e.target.value)}
                    className="input"
                    style={{ paddingLeft: 32, fontSize: '0.82rem' }}
                  />
                </div>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                  Showing {filteredDisclosures.length} of {disclosures.length} disclosures
                </span>
              </div>

              {/* Disclosures Table */}
              <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
                    <thead>
                      <tr style={{ background: 'rgba(30, 41, 59, 0.7)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)' }}>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Disclosure ID</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600, minWidth: 260 }}>Disclosure Text</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Associated Product</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Market</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600, minWidth: 200 }}>Applies When</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600 }}>Effective Dates</th>
                        <th style={{ padding: '10px 14px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredDisclosures.length === 0 ? (
                        <tr>
                          <td colSpan={7} style={{ padding: 36, textAlign: 'center', color: 'var(--text-dim)' }}>
                            <AlertCircle size={32} style={{ margin: '0 auto 8px', opacity: 0.5 }} />
                            <div>No required disclosures found matching the criteria.</div>
                            {disclosures.length === 0 && (
                              <button
                                onClick={() => setExcelModalOpen(true)}
                                className="btn btn-secondary"
                                style={{ marginTop: 12, fontSize: '0.8rem' }}
                              >
                                <FileSpreadsheet size={14} style={{ marginRight: 6 }} /> Import Disclosures
                              </button>
                            )}
                          </td>
                        </tr>
                      ) : (
                        filteredDisclosures.map((d) => (
                          <tr
                            key={d.id}
                            style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}
                            className="table-row-hover"
                          >
                            <td style={{ padding: '10px 14px' }}>
                              <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#f59e0b', background: 'rgba(245, 158, 11, 0.1)', padding: '2px 6px', borderRadius: 4 }}>
                                {d.disclosure_id}
                              </span>
                            </td>
                            <td style={{ padding: '10px 14px', color: '#f8fafc', maxWidth: 360 }}>
                              <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {d.disclosure_text}
                              </div>
                            </td>
                            <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: '0.78rem', color: '#93c5fd' }}>
                              {d.applicable_product_id}
                            </td>
                            <td style={{ padding: '10px 14px', color: 'var(--text-sub)' }}>
                              {d.applicable_market}
                            </td>
                            <td style={{ padding: '10px 14px', color: '#fde68a', fontSize: '0.78rem' }}>
                              <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 220 }}>
                                {d.applies_when}
                              </div>
                            </td>
                            <td style={{ padding: '10px 14px', color: 'var(--text-dim)', fontSize: '0.75rem' }}>
                              {d.effective_from} → {d.effective_until || 'Indefinite'}
                            </td>
                            <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                              <button
                                onClick={() => setSelectedDisclosure(d)}
                                className="btn btn-secondary"
                                style={{ padding: '4px 10px', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                              >
                                <Eye size={12} /> View Details
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ===================================================================== */}
      {/* PRIMARY TAB 2: BRAND ASSETS */}
      {/* ===================================================================== */}
      {activeTab === 'assets' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Header & Upload Action */}
          <div className="flex-between" style={{ alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.15rem', color: '#fff' }}>Official Brand Assets & Logos</h3>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.82rem', color: 'var(--text-dim)' }}>
                Approved brand logos, product photography, and reference graphics. These assets power automated visual governance checks.
              </p>
            </div>
            {isReviewer && (
              <button
                onClick={() => {
                  setAssetFile(null);
                  setAssetTitle('');
                  setAssetCategory('logo');
                  setAssetUsageNotes('');
                  setAssetModalOpen(true);
                }}
                className="btn btn-primary"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' }}
              >
                <Upload size={14} /> Upload Brand Asset
              </button>
            )}
          </div>

          {/* Primary Logo Activation Readiness Banner */}
          {approvedPrimaryLogo ? (
            <div style={{ padding: '14px 18px', background: 'rgba(34, 197, 94, 0.1)', borderRadius: 10, border: '1px solid rgba(34, 197, 94, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <CheckCircle size={22} color="#4ade80" />
                <div>
                  <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#f0fdf4' }}>
                    ⭐ Primary Brand Logo Approved & Activation-Ready
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#bbf7d0', marginTop: 2 }}>
                    "{approvedPrimaryLogo.asset_name}" is active. Visual governance will enforce logo presence, {approvedPrimaryLogo.min_clearance_px || 20}px minimum clearance, and aspect ratio integrity.
                  </div>
                </div>
              </div>
              <span className="badge badge-success">Ready for Activation</span>
            </div>
          ) : anyLogo ? (
            <div style={{ padding: '14px 18px', background: 'rgba(245, 158, 11, 0.1)', borderRadius: 10, border: '1px solid rgba(245, 158, 11, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <AlertTriangle size={22} color="#fbbf24" />
                <div>
                  <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#fffbeb' }}>
                    Primary Logo Uploaded but Pending Approval
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#fde68a', marginTop: 2 }}>
                    A logo asset has been uploaded ({anyLogo.asset_name}) but has not been approved yet. Please approve it below before activating a new Knowledge Base version.
                  </div>
                </div>
              </div>
              {isReviewer && anyLogo.status === 'pending_review' && (
                <button
                  onClick={() => handleReviewAsset(anyLogo.id, 'approved')}
                  className="btn btn-success"
                  style={{ fontSize: '0.8rem', padding: '6px 14px', whiteSpace: 'nowrap' }}
                >
                  <Check size={14} style={{ marginRight: 6 }} /> Approve Logo
                </button>
              )}
            </div>
          ) : (
            <div style={{ padding: '14px 18px', background: 'rgba(245, 158, 11, 0.1)', borderRadius: 10, border: '1px solid rgba(245, 158, 11, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <AlertTriangle size={22} color="#fbbf24" />
                <div>
                  <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#fffbeb' }}>
                    Primary Logo Missing — Required for Activation Readiness
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#fde68a', marginTop: 2 }}>
                    An approved Primary Logo is strongly recommended for visual governance and automated template matching before activating a new Knowledge Base version.
                  </div>
                </div>
              </div>
              {isReviewer && (
                <button
                  onClick={() => {
                    setAssetFile(null);
                    setAssetTitle('');
                    setAssetCategory('logo');
                    setAssetUsageNotes('');
                    setAssetModalOpen(true);
                  }}
                  className="btn btn-primary"
                  style={{ fontSize: '0.8rem', padding: '6px 14px', whiteSpace: 'nowrap' }}
                >
                  <Upload size={14} style={{ marginRight: 6 }} /> Upload Primary Logo
                </button>
              )}
            </div>
          )}

          {/* Filter Bar for Assets */}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <select
              value={assetCategoryFilter}
              onChange={(e) => setAssetCategoryFilter(e.target.value)}
              className="input"
              style={{ width: 220, fontSize: '0.82rem' }}
            >
              <option value="all">All Asset Categories</option>
              <option value="logo">⭐ Primary Logo</option>
              <option value="product_image">Product Images</option>
              <option value="brand_graphic">Brand Graphics</option>
              <option value="approved_asset">Other Approved Assets</option>
            </select>
            <select
              value={assetStatusFilter}
              onChange={(e) => setAssetStatusFilter(e.target.value)}
              className="input"
              style={{ width: 160, fontSize: '0.82rem' }}
            >
              <option value="all">All Statuses</option>
              <option value="approved">Approved</option>
              <option value="pending_review">Pending Review</option>
              <option value="rejected">Rejected</option>
            </select>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
              Showing {filteredAssets.length} of {assets.length} assets
            </span>
          </div>

          {/* Asset Card Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
            {filteredAssets.length === 0 ? (
              <div className="card" style={{ gridColumn: '1 / -1', textAlign: 'center', padding: 48, color: 'var(--text-dim)' }}>
                <ImageIcon size={36} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
                <h4 style={{ color: '#f8fafc', marginBottom: 6 }}>No Brand Assets Found</h4>
                <p style={{ fontSize: '0.82rem', maxWidth: 400, margin: '0 auto 16px' }}>
                  Upload your brand's primary logo, packaging photography, or graphic assets to enable automated visual governance.
                </p>
                {isReviewer && (
                  <button
                    onClick={() => {
                      setAssetFile(null);
                      setAssetTitle('');
                      setAssetCategory('logo');
                      setAssetUsageNotes('');
                      setAssetModalOpen(true);
                    }}
                    className="btn btn-primary"
                    style={{ fontSize: '0.82rem' }}
                  >
                    <Upload size={14} style={{ marginRight: 6 }} /> Upload Primary Logo
                  </button>
                )}
              </div>
            ) : (
              filteredAssets.map((asset) => {
                const isLogo = asset.asset_type === 'logo' || asset.asset_name.toLowerCase().includes('logo');
                const fileUrl = api.getAssetFileUrl(asset.id);

                return (
                  <div
                    key={asset.id}
                    className="card"
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      border: isLogo && asset.status === 'approved' ? '1px solid rgba(234, 179, 8, 0.4)' : undefined,
                      boxShadow: isLogo && asset.status === 'approved' ? '0 0 15px rgba(234, 179, 8, 0.1)' : undefined
                    }}
                  >
                    <div>
                      {/* Thumbnail Preview */}
                      <div
                        style={{
                          height: 150,
                          borderRadius: 6,
                          background: '#090d16',
                          border: '1px solid var(--border-subtle)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          overflow: 'hidden',
                          marginBottom: 12,
                          position: 'relative'
                        }}
                      >
                        <img
                          src={fileUrl}
                          alt={asset.asset_name}
                          style={{
                            maxWidth: '100%',
                            maxHeight: '100%',
                            objectFit: 'contain',
                            padding: 8
                          }}
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                      </div>

                      {/* Badges Bar */}
                      <div className="flex-between" style={{ marginBottom: 8, flexWrap: 'wrap', gap: 6 }}>
                        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                          {isLogo && (
                            <span style={{ background: 'rgba(234, 179, 8, 0.2)', color: '#facc15', border: '1px solid rgba(234, 179, 8, 0.4)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600 }}>
                              ⭐ Primary Logo
                            </span>
                          )}
                          <span className="badge badge-neutral" style={{ fontSize: '0.7rem' }}>
                            {asset.asset_type.replace(/_/g, ' ')}
                          </span>
                        </div>
                        <StatusBadge status={asset.status} />
                      </div>

                      {/* Asset Title */}
                      <div style={{ fontWeight: 600, fontSize: '0.92rem', color: '#fff', marginBottom: 6 }}>
                        {asset.asset_name}
                      </div>

                      {/* Specs */}
                      <div style={{ fontSize: '0.74rem', color: 'var(--text-dim)', marginBottom: 8, display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <div>
                          MIME: {asset.mime_type} {asset.width ? `• ${asset.width}x${asset.height}px` : ''}
                        </div>
                        <div>
                          Clearance: <strong>{asset.min_clearance_px || 20}px</strong> | Aspect Ratio: <strong>{asset.aspect_ratio || 'N/A'}</strong>
                        </div>
                        <div>
                          Uploaded: {new Date(asset.created_at).toLocaleDateString()}
                        </div>
                      </div>

                      {/* Usage Instructions / Notes */}
                      {asset.usage_notes && (
                        <div style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '8px 10px', borderRadius: 6, border: '1px solid rgba(255, 255, 255, 0.08)', marginBottom: 12 }}>
                          <div style={{ fontSize: '0.7rem', fontWeight: 600, color: '#93c5fd', marginBottom: 2 }}>
                            Usage Guidelines:
                          </div>
                          <div style={{ fontSize: '0.75rem', color: '#e2e8f0', lineHeight: 1.4 }}>
                            {asset.usage_notes}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Review and Actions Bar */}
                    <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.06)', paddingTop: 10, marginTop: 10, display: 'flex', gap: 8, justifyContent: 'space-between', alignItems: 'center' }}>
                      {isReviewer && asset.status === 'pending_review' ? (
                        <div style={{ display: 'flex', gap: 6, flex: 1 }}>
                          <button
                            onClick={() => handleReviewAsset(asset.id, 'approved')}
                            className="btn btn-success"
                            style={{ flex: 1, padding: '5px 8px', fontSize: '0.75rem' }}
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleReviewAsset(asset.id, 'rejected')}
                            className="btn btn-danger"
                            style={{ flex: 1, padding: '5px 8px', fontSize: '0.75rem' }}
                          >
                            Reject
                          </button>
                        </div>
                      ) : (
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                          Status: {asset.status}
                        </div>
                      )}

                      {isReviewer && (
                        <button
                          onClick={() => handleDeleteAsset(asset.id)}
                          className="btn btn-secondary"
                          style={{ padding: '5px 8px', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.3)' }}
                          title="Delete asset"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* PRIMARY TAB 3: UPLOADED SOURCES */}
      {/* ===================================================================== */}
      {activeTab === 'sources' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Header & Upload Document Action */}
          <div className="flex-between" style={{ alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.15rem', color: '#fff' }}>Uploaded Source Documents & Excel Imports</h3>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.82rem', color: 'var(--text-dim)' }}>
                Audit trail of original files uploaded by your organisation: Brand Guidelines PDFs, Excel Catalogues, Claims Registers, and Supporting Evidence.
              </p>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
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
              <button
                onClick={() => setExcelModalOpen(true)}
                className="btn btn-secondary"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.82rem' }}
              >
                <FileSpreadsheet size={14} color="#34d399" /> Import Excel Catalogue
              </button>
            </div>
          </div>

          {/* Section 1: Excel Bulk Import Sessions */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <FileSpreadsheet size={16} color="#34d399" />
              <h4 style={{ margin: 0, fontSize: '0.98rem', color: '#f8fafc' }}>
                Bulk Excel Catalogues & Registers ({stagedImports.length})
              </h4>
            </div>

            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
                  <thead>
                    <tr style={{ background: 'rgba(30, 41, 59, 0.7)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)' }}>
                      <th style={{ padding: '10px 14px', fontWeight: 600 }}>File Name</th>
                      <th style={{ padding: '10px 14px', fontWeight: 600 }}>File Type</th>
                      <th style={{ padding: '10px 14px', fontWeight: 600 }}>Source Category</th>
                      <th style={{ padding: '10px 14px', fontWeight: 600 }}>Upload Date</th>
                      <th style={{ padding: '10px 14px', fontWeight: 600 }}>Uploaded By</th>
                      <th style={{ padding: '10px 14px', fontWeight: 600 }}>Import Status</th>
                      <th style={{ padding: '10px 14px', fontWeight: 600, textAlign: 'center' }}>Accepted Rows</th>
                      <th style={{ padding: '10px 14px', fontWeight: 600, textAlign: 'center' }}>Rejected Rows</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stagedImports.length === 0 ? (
                      <tr>
                        <td colSpan={8} style={{ padding: 28, textAlign: 'center', color: 'var(--text-dim)' }}>
                          No bulk Excel imports uploaded yet. Use "Import Excel" to upload product catalogues or claims registers.
                        </td>
                      </tr>
                    ) : (
                      stagedImports.map((imp) => {
                        const categoryLabel =
                          imp.import_type === 'product_catalogue'
                            ? 'Product Catalogue'
                            : imp.has_disclosures
                            ? 'Claims & Disclosures Register'
                            : 'Claims Register';

                        return (
                          <tr
                            key={imp.id}
                            style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}
                            className="table-row-hover"
                          >
                            <td style={{ padding: '10px 14px', fontWeight: 600, color: '#f8fafc' }}>
                              {imp.file_name}
                            </td>
                            <td style={{ padding: '10px 14px' }}>
                              <span style={{ fontFamily: 'monospace', fontSize: '0.74rem', background: 'rgba(16, 185, 129, 0.1)', color: '#34d399', padding: '2px 6px', borderRadius: 4 }}>
                                .xlsx spreadsheet
                              </span>
                            </td>
                            <td style={{ padding: '10px 14px', color: 'var(--text-sub)' }}>
                              {categoryLabel}
                            </td>
                            <td style={{ padding: '10px 14px', color: 'var(--text-dim)', fontSize: '0.75rem' }}>
                              {imp.created_at ? new Date(imp.created_at).toLocaleString() : '—'}
                            </td>
                            <td style={{ padding: '10px 14px', color: 'var(--text-sub)' }}>
                              {imp.created_by_name || 'System / Admin'}
                            </td>
                            <td style={{ padding: '10px 14px' }}>
                              <span className={`badge ${imp.status === 'committed' ? 'badge-success' : imp.status === 'pending_preview' ? 'badge-warning' : 'badge-neutral'}`}>
                                {imp.status === 'committed' ? 'Committed' : imp.status === 'pending_preview' ? 'Preview Staged' : imp.status}
                              </span>
                            </td>
                            <td style={{ padding: '10px 14px', textAlign: 'center', fontWeight: 600, color: '#4ade80' }}>
                              {imp.valid_rows}
                            </td>
                            <td style={{ padding: '10px 14px', textAlign: 'center', fontWeight: 600, color: imp.error_rows > 0 ? '#f87171' : 'var(--text-dim)' }}>
                              {imp.error_rows}
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

          {/* Section 2: Reference Guidelines & Documents */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <FileText size={16} color="#818cf8" />
              <h4 style={{ margin: 0, fontSize: '0.98rem', color: '#f8fafc' }}>
                Brand Guidelines & Reference Documentation ({sources.length})
              </h4>
            </div>

            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
                  <thead>
                    <tr style={{ background: 'rgba(30, 41, 59, 0.7)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)' }}>
                      <th style={{ padding: '10px 14px', fontWeight: 600 }}>File Name</th>
                      <th style={{ padding: '10px 14px', fontWeight: 600 }}>File Type</th>
                      <th style={{ padding: '10px 14px', fontWeight: 600 }}>Source Category</th>
                      <th style={{ padding: '10px 14px', fontWeight: 600 }}>Upload Date</th>
                      <th style={{ padding: '10px 14px', fontWeight: 600 }}>Status</th>
                      <th style={{ padding: '10px 14px', fontWeight: 600, textAlign: 'center' }}>Extracted Knowledge</th>
                      <th style={{ padding: '10px 14px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sources.length === 0 ? (
                      <tr>
                        <td colSpan={7} style={{ padding: 28, textAlign: 'center', color: 'var(--text-dim)' }}>
                          No reference PDF documents uploaded yet.
                        </td>
                      </tr>
                    ) : (
                      sources.map((src) => {
                        const isPdf = src.mime_type.includes('pdf') || src.filename.toLowerCase().endsWith('.pdf');
                        const downloadUrl = api.getSourceDownloadUrl(src.id);

                        return (
                          <tr
                            key={src.id}
                            style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}
                            className="table-row-hover"
                          >
                            <td style={{ padding: '10px 14px', fontWeight: 600, color: '#f8fafc' }}>
                              {src.filename}
                            </td>
                            <td style={{ padding: '10px 14px' }}>
                              <span style={{ fontFamily: 'monospace', fontSize: '0.74rem', background: 'rgba(99, 102, 241, 0.1)', color: '#818cf8', padding: '2px 6px', borderRadius: 4 }}>
                                {isPdf ? 'PDF' : src.mime_type.split('/')[1] || src.mime_type}
                              </span>
                            </td>
                            <td style={{ padding: '10px 14px', color: 'var(--text-sub)' }}>
                              {src.source_type.replace(/_/g, ' ').toUpperCase()}
                            </td>
                            <td style={{ padding: '10px 14px', color: 'var(--text-dim)', fontSize: '0.75rem' }}>
                              {new Date(src.created_at).toLocaleString()}
                            </td>
                            <td style={{ padding: '10px 14px' }}>
                              <StatusBadge status={src.status} />
                            </td>
                            <td style={{ padding: '10px 14px', textAlign: 'center', color: 'var(--text-sub)' }}>
                              {src.rules_count || 0} rules, {src.facts_count || 0} facts
                            </td>
                            <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                              <div style={{ display: 'inline-flex', gap: 6 }}>
                                {isPdf && (
                                  <button
                                    onClick={() => handleOpenViewText(src.id)}
                                    className="btn btn-secondary"
                                    style={{ padding: '4px 8px', fontSize: '0.74rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                                    title="Inspect extracted text"
                                  >
                                    <Eye size={12} /> View Text
                                  </button>
                                )}
                                <a
                                  href={downloadUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="btn btn-secondary"
                                  style={{ padding: '4px 8px', fontSize: '0.74rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                                  title="Download original document"
                                >
                                  <Download size={12} /> Download
                                </a>
                                {isReviewer && isPdf && (
                                  <button
                                    onClick={() => handleReprocessSource(src.id)}
                                    disabled={reprocessingId === src.id}
                                    className="btn btn-secondary"
                                    style={{ padding: '4px 8px', fontSize: '0.74rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                                    title="Reprocess with Gemini"
                                  >
                                    <RefreshCw size={12} className={reprocessingId === src.id ? 'spin' : ''} /> Reprocess
                                  </button>
                                )}
                              </div>
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
        </div>
      )}

      {/* ===================================================================== */}
      {/* DETAIL MODAL: PRODUCT */}
      {/* ===================================================================== */}
      {selectedProduct && (
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
          <div className="card" style={{ width: 680, maxHeight: '90vh', overflowY: 'auto', background: '#131b2e', border: '1px solid rgba(59, 130, 246, 0.4)' }}>
            <div className="flex-between" style={{ marginBottom: 16, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12 }}>
              <div>
                <h2 className="title-md" style={{ color: '#fff' }}>{selectedProduct.product_name}</h2>
                <div style={{ display: 'flex', gap: 8, marginTop: 4, alignItems: 'center' }}>
                  <span style={{ fontFamily: 'monospace', color: '#93c5fd', fontSize: '0.8rem', background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: 4 }}>
                    ID: {selectedProduct.product_id}
                  </span>
                  <span className="badge badge-success">{selectedProduct.record_status}</span>
                  <span className="badge badge-neutral">{selectedProduct.offering_type}</span>
                </div>
              </div>
              <button onClick={() => setSelectedProduct(null)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14, fontSize: '0.85rem' }}>
              <div>
                <strong style={{ color: '#93c5fd' }}>Category & Market:</strong>
                <div style={{ color: '#e2e8f0', marginTop: 2 }}>{selectedProduct.product_category} — Market: {selectedProduct.applicable_market}</div>
              </div>

              {selectedProduct.sku && (
                <div>
                  <strong style={{ color: '#93c5fd' }}>SKU / Variant:</strong>
                  <div style={{ color: '#e2e8f0', marginTop: 2 }}>{selectedProduct.sku} {selectedProduct.variant_name ? `(${selectedProduct.variant_name})` : ''}</div>
                </div>
              )}

              {selectedProduct.pack_size && (
                <div>
                  <strong style={{ color: '#93c5fd' }}>Pack Size / Unit:</strong>
                  <div style={{ color: '#e2e8f0', marginTop: 2 }}>{selectedProduct.pack_size} {selectedProduct.pack_unit || ''}</div>
                </div>
              )}

              <div>
                <strong style={{ color: '#93c5fd' }}>Product Description:</strong>
                <div style={{ color: '#cbd5e1', marginTop: 2, lineHeight: 1.5 }}>{selectedProduct.product_description}</div>
              </div>

              {selectedProduct.ingredients_components && (
                <div>
                  <strong style={{ color: '#93c5fd' }}>Ingredients / Formulation Components:</strong>
                  <div style={{ color: '#cbd5e1', marginTop: 2, lineHeight: 1.5, background: 'rgba(0,0,0,0.2)', padding: 10, borderRadius: 6 }}>
                    {selectedProduct.ingredients_components}
                  </div>
                </div>
              )}

              {selectedProduct.key_features && (
                <div>
                  <strong style={{ color: '#93c5fd' }}>Key Features:</strong>
                  <div style={{ color: '#cbd5e1', marginTop: 2, lineHeight: 1.5, background: 'rgba(0,0,0,0.2)', padding: 10, borderRadius: 6 }}>
                    {selectedProduct.key_features}
                  </div>
                </div>
              )}

              {selectedProduct.specifications && (
                <div>
                  <strong style={{ color: '#93c5fd' }}>Technical Specifications:</strong>
                  <div style={{ color: '#cbd5e1', marginTop: 2, lineHeight: 1.5, background: 'rgba(0,0,0,0.2)', padding: 10, borderRadius: 6 }}>
                    {selectedProduct.specifications}
                  </div>
                </div>
              )}

              {selectedProduct.known_limitations && (
                <div>
                  <strong style={{ color: '#f87171' }}>Known Limitations & Warnings:</strong>
                  <div style={{ color: '#fca5a5', marginTop: 2, lineHeight: 1.5, background: 'rgba(239, 68, 68, 0.1)', padding: 10, borderRadius: 6, border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                    {selectedProduct.known_limitations}
                  </div>
                </div>
              )}
            </div>

            <div style={{ marginTop: 20, textAlign: 'right' }}>
              <button onClick={() => setSelectedProduct(null)} className="btn btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* DETAIL MODAL: CLAIM */}
      {/* ===================================================================== */}
      {selectedClaim && (
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
          <div className="card" style={{ width: 680, maxHeight: '90vh', overflowY: 'auto', background: '#131b2e', border: '1px solid rgba(99, 102, 241, 0.4)' }}>
            <div className="flex-between" style={{ marginBottom: 16, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12 }}>
              <div>
                <h2 className="title-md" style={{ color: '#fff' }}>Claim Details</h2>
                <div style={{ display: 'flex', gap: 8, marginTop: 4, alignItems: 'center' }}>
                  <span style={{ fontFamily: 'monospace', color: '#a5b4fc', fontSize: '0.8rem', background: 'rgba(99, 102, 241, 0.1)', padding: '2px 6px', borderRadius: 4 }}>
                    ID: {selectedClaim.claim_id}
                  </span>
                  <span className={`badge ${selectedClaim.claim_status === 'Approved' ? 'badge-success' : selectedClaim.claim_status === 'Restricted' ? 'badge-warning' : 'badge-danger'}`}>
                    {selectedClaim.claim_status}
                  </span>
                  <span className="badge badge-neutral">{selectedClaim.claim_type}</span>
                </div>
              </div>
              <button onClick={() => setSelectedClaim(null)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14, fontSize: '0.85rem' }}>
              <div>
                <strong style={{ color: '#a5b4fc' }}>Authoritative Claim Text:</strong>
                <div style={{ color: '#f8fafc', fontSize: '0.95rem', fontWeight: 500, marginTop: 4, background: 'rgba(0,0,0,0.2)', padding: 12, borderRadius: 6, lineHeight: 1.5 }}>
                  "{selectedClaim.claim_text}"
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <strong style={{ color: '#a5b4fc' }}>Associated Product:</strong>
                  <div style={{ color: '#e2e8f0', marginTop: 2, fontFamily: 'monospace' }}>{selectedClaim.applicable_product_id}</div>
                </div>
                <div>
                  <strong style={{ color: '#a5b4fc' }}>Applicable Market:</strong>
                  <div style={{ color: '#e2e8f0', marginTop: 2 }}>{selectedClaim.applicable_market}</div>
                </div>
              </div>

              <div>
                <strong style={{ color: '#a5b4fc' }}>Effective Validity Period:</strong>
                <div style={{ color: '#e2e8f0', marginTop: 2 }}>
                  From: {selectedClaim.effective_from} → Until: {selectedClaim.effective_until || 'Indefinite'}
                </div>
              </div>

              {selectedClaim.approved_variations && (
                <div>
                  <strong style={{ color: '#4ade80' }}>Approved Variations:</strong>
                  <div style={{ color: '#bbf7d0', marginTop: 2, lineHeight: 1.5, background: 'rgba(34, 197, 94, 0.08)', padding: 10, borderRadius: 6, border: '1px solid rgba(34, 197, 94, 0.2)' }}>
                    {selectedClaim.approved_variations}
                  </div>
                </div>
              )}

              {selectedClaim.restricted_conditions && (
                <div>
                  <strong style={{ color: '#fbbf24' }}>Restricted Conditions & Provisos:</strong>
                  <div style={{ color: '#fde68a', marginTop: 2, lineHeight: 1.5, background: 'rgba(245, 158, 11, 0.08)', padding: 10, borderRadius: 6, border: '1px solid rgba(245, 158, 11, 0.2)' }}>
                    {selectedClaim.restricted_conditions}
                  </div>
                </div>
              )}

              {selectedClaim.prohibited_variations && (
                <div>
                  <strong style={{ color: '#f87171' }}>Prohibited Phrasings / Variations:</strong>
                  <div style={{ color: '#fca5a5', marginTop: 2, lineHeight: 1.5, background: 'rgba(239, 68, 68, 0.08)', padding: 10, borderRadius: 6, border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                    {selectedClaim.prohibited_variations}
                  </div>
                </div>
              )}
            </div>

            <div style={{ marginTop: 20, textAlign: 'right' }}>
              <button onClick={() => setSelectedClaim(null)} className="btn btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* DETAIL MODAL: REQUIRED DISCLOSURE */}
      {/* ===================================================================== */}
      {selectedDisclosure && (
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
          <div className="card" style={{ width: 680, maxHeight: '90vh', overflowY: 'auto', background: '#131b2e', border: '1px solid rgba(245, 158, 11, 0.4)' }}>
            <div className="flex-between" style={{ marginBottom: 16, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12 }}>
              <div>
                <h2 className="title-md" style={{ color: '#fff' }}>Required Disclosure Details</h2>
                <div style={{ display: 'flex', gap: 8, marginTop: 4, alignItems: 'center' }}>
                  <span style={{ fontFamily: 'monospace', color: '#f59e0b', fontSize: '0.8rem', background: 'rgba(245, 158, 11, 0.1)', padding: '2px 6px', borderRadius: 4 }}>
                    ID: {selectedDisclosure.disclosure_id}
                  </span>
                  <span className="badge badge-warning">Mandatory Disclosure</span>
                </div>
              </div>
              <button onClick={() => setSelectedDisclosure(null)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14, fontSize: '0.85rem' }}>
              <div>
                <strong style={{ color: '#fbbf24' }}>Mandatory Disclosure Text:</strong>
                <div style={{ color: '#fef3c7', fontSize: '0.95rem', fontWeight: 500, marginTop: 4, background: 'rgba(245, 158, 11, 0.08)', padding: 12, borderRadius: 6, border: '1px solid rgba(245, 158, 11, 0.2)', lineHeight: 1.5 }}>
                  "{selectedDisclosure.disclosure_text}"
                </div>
              </div>

              <div>
                <strong style={{ color: '#fbbf24' }}>Trigger Condition (Applies When):</strong>
                <div style={{ color: '#e2e8f0', marginTop: 2, background: 'rgba(0,0,0,0.2)', padding: 10, borderRadius: 6 }}>
                  {selectedDisclosure.applies_when}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <strong style={{ color: '#fbbf24' }}>Associated Product:</strong>
                  <div style={{ color: '#e2e8f0', marginTop: 2, fontFamily: 'monospace' }}>{selectedDisclosure.applicable_product_id}</div>
                </div>
                <div>
                  <strong style={{ color: '#fbbf24' }}>Applicable Market:</strong>
                  <div style={{ color: '#e2e8f0', marginTop: 2 }}>{selectedDisclosure.applicable_market}</div>
                </div>
              </div>

              <div>
                <strong style={{ color: '#fbbf24' }}>Effective Validity Period:</strong>
                <div style={{ color: '#e2e8f0', marginTop: 2 }}>
                  From: {selectedDisclosure.effective_from} → Until: {selectedDisclosure.effective_until || 'Indefinite'}
                </div>
              </div>
            </div>

            <div style={{ marginTop: 20, textAlign: 'right' }}>
              <button onClick={() => setSelectedDisclosure(null)} className="btn btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODAL: UPLOAD BRAND ASSET (Primary Logo, Product Images, Graphics) */}
      {/* ===================================================================== */}
      {assetModalOpen && (
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
          <div className="card" style={{ width: 560, background: '#131b2e', border: '1px solid rgba(99, 102, 241, 0.4)' }}>
            <div className="flex-between" style={{ marginBottom: 16 }}>
              <div>
                <h2 className="title-md">Upload Brand Asset</h2>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                  Upload official brand logos, product photography, or approved graphics.
                </span>
              </div>
              <button onClick={() => setAssetModalOpen(false)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleUploadAsset}>
              {/* Category selector */}
              <div className="form-group" style={{ marginBottom: 14 }}>
                <label className="form-label">Asset Category</label>
                <select
                  value={assetCategory}
                  onChange={(e: any) => setAssetCategory(e.target.value)}
                  className="input"
                  required
                >
                  <option value="logo">⭐ Primary Logo (Mandatory for Visual Governance)</option>
                  <option value="product_image">Product Image (Packshot / Variant)</option>
                  <option value="brand_graphic">Brand Graphic (Badge, Icon, Creative)</option>
                  <option value="approved_asset">Other Approved Asset</option>
                </select>
              </div>

              {/* Asset Name */}
              <div className="form-group" style={{ marginBottom: 14 }}>
                <label className="form-label">Asset Name</label>
                <input
                  type="text"
                  placeholder="e.g. Primary Brand Logo - Dark Horizontal"
                  value={assetTitle}
                  onChange={(e) => setAssetTitle(e.target.value)}
                  className="input"
                />
              </div>

              {/* File input */}
              <div className="form-group" style={{ marginBottom: 14 }}>
                <label className="form-label">File (PNG, SVG, JPG, WEBP)</label>
                <input
                  type="file"
                  accept="image/png,image/svg+xml,image/jpeg,image/webp"
                  onChange={(e) => setAssetFile(e.target.files?.[0] || null)}
                  className="input"
                  required
                />
              </div>

              {/* Usage Instructions / Notes */}
              <div className="form-group" style={{ marginBottom: 16 }}>
                <label className="form-label">Usage Instructions / Placement Rules (Optional)</label>
                <textarea
                  placeholder="e.g. Minimum clear space 20px. Must not be placed on clashing backgrounds. Use horizontal orientation on desktop."
                  value={assetUsageNotes}
                  onChange={(e) => setAssetUsageNotes(e.target.value)}
                  className="input"
                  rows={3}
                />
              </div>

              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => setAssetModalOpen(false)}
                  className="btn btn-secondary"
                  disabled={uploadingAsset}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={uploadingAsset || !assetFile}
                >
                  {uploadingAsset ? 'Uploading...' : 'Upload Asset'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODAL: UPLOAD REFERENCE DOCUMENT (PDF Brand Guidelines, Supporting Docs) */}
      {/* ===================================================================== */}
      {sourceModalOpen && (
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
          <div className="card" style={{ width: 540, background: '#131b2e', border: '1px solid rgba(99, 102, 241, 0.4)' }}>
            <div className="flex-between" style={{ marginBottom: 16 }}>
              <div>
                <h2 className="title-md">Upload Reference Document</h2>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                  Brand guidelines PDFs or supporting regulatory documents.
                </span>
              </div>
              <button onClick={() => setSourceModalOpen(false)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleUploadSource}>
              <div className="form-group" style={{ marginBottom: 14 }}>
                <label className="form-label">Document Category</label>
                <select
                  value={sourceType}
                  onChange={(e) => setSourceType(e.target.value)}
                  className="input"
                >
                  <option value="pdf_brand_guidelines">PDF Brand Guidelines</option>
                  <option value="pdf_product_knowledge">PDF Product Knowledge & Specs</option>
                  <option value="supporting_doc">Supporting Evidence Document</option>
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: 14 }}>
                <label className="form-label">Document Title</label>
                <input
                  type="text"
                  placeholder="e.g. Master Brand Style & Compliance Guide 2026"
                  value={sourceTitle}
                  onChange={(e) => setSourceTitle(e.target.value)}
                  className="input"
                />
              </div>

              <div className="form-group" style={{ marginBottom: 16 }}>
                <label className="form-label">File (PDF)</label>
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => setSourceFile(e.target.files?.[0] || null)}
                  className="input"
                  required
                />
              </div>

              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => setSourceModalOpen(false)}
                  className="btn btn-secondary"
                  disabled={uploadingSource}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={uploadingSource || !sourceFile}
                >
                  {uploadingSource ? 'Uploading...' : 'Upload Document'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODAL: VIEW EXTRACTED TEXT FROM PDF */}
      {/* ===================================================================== */}
      {viewTextModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100,
          padding: 20
        }}>
          <div className="card" style={{ width: 800, maxHeight: '90vh', display: 'flex', flexDirection: 'column', background: '#131b2e', border: '1px solid rgba(99, 102, 241, 0.4)' }}>
            <div className="flex-between" style={{ marginBottom: 14, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 10 }}>
              <div>
                <h2 className="title-md">{viewTextData?.title || 'Document Text Viewer'}</h2>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                  {viewTextData?.filename} • {viewTextData?.total_pages || 0} pages • {viewTextData?.total_characters || 0} characters
                </span>
              </div>
              <button onClick={() => setViewTextModalOpen(false)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            {loadingText ? (
              <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-dim)' }}>
                <RefreshCw size={24} className="spin" style={{ margin: '0 auto 12px' }} />
                Loading document text...
              </div>
            ) : viewTextData ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, flex: 1, minHeight: 0 }}>
                {/* Page Selector */}
                {viewTextData.pages && viewTextData.pages.length > 1 && (
                  <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 6 }}>
                    {viewTextData.pages.map((p: any) => (
                      <button
                        key={p.page_number}
                        onClick={() => setSelectedTextPage(p.page_number)}
                        className={`btn ${selectedTextPage === p.page_number ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                      >
                        Page {p.page_number}
                      </button>
                    ))}
                  </div>
                )}

                {/* Page Content */}
                <div style={{
                  flex: 1,
                  overflowY: 'auto',
                  background: 'rgba(0,0,0,0.3)',
                  padding: 16,
                  borderRadius: 6,
                  fontFamily: 'monospace',
                  fontSize: '0.82rem',
                  lineHeight: 1.6,
                  whiteSpace: 'pre-wrap',
                  color: '#e2e8f0'
                }}>
                  {viewTextData.pages?.find((p: any) => p.page_number === selectedTextPage)?.text || viewTextData.full_text || 'No text extracted.'}
                </div>
              </div>
            ) : null}

            <div style={{ marginTop: 14, textAlign: 'right' }}>
              <button onClick={() => setViewTextModalOpen(false)} className="btn btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODAL: RELOCATED POLICY IMPACT RESCORING HUB */}
      {/* ===================================================================== */}
      {rescoreModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100,
          padding: 20
        }}>
          <div className="card" style={{ width: 900, maxHeight: '92vh', overflowY: 'auto', background: '#131b2e', border: '1px solid rgba(167, 139, 250, 0.4)' }}>
            <div className="flex-between" style={{ marginBottom: 16, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <RefreshCw size={20} color="#c084fc" />
                <div>
                  <h2 className="title-md" style={{ color: '#fff', margin: 0 }}>Policy Impact Rescoring Hub</h2>
                  <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    Non-destructive simulation: Evaluate your historical content assets against newly activated brand knowledge manifests.
                  </p>
                </div>
              </div>
              <button onClick={() => setRescoreModalOpen(false)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            {/* Simulation Trigger Bar */}
            <div className="card" style={{ background: 'rgba(30, 27, 75, 0.5)', border: '1px solid rgba(99, 102, 241, 0.3)', marginBottom: 20 }}>
              <div className="flex-between" style={{ alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>
                    Simulate Historical Content Catalog
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                    Original governance runs and baseline audit trails remain permanently untouched.
                  </div>
                </div>

                {isReviewer && (
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <select
                      value={selectedKbVersionId}
                      onChange={(e) => setSelectedKbVersionId(e.target.value)}
                      className="input"
                      style={{ fontSize: '0.8rem', padding: '6px 10px', minWidth: 200 }}
                    >
                      <option value="">Active Version (Default)</option>
                      {kbVersions.map((v: any) => (
                        <option key={v.id} value={v.id}>
                          Version {v.version_num} ({v.version_tag || 'Standard'}) {v.is_active ? '• Active' : ''}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={handleTriggerRescore}
                      disabled={rescoringTriggering}
                      className="btn btn-primary"
                      style={{ fontSize: '0.82rem', padding: '7px 14px', display: 'inline-flex', alignItems: 'center', gap: 6 }}
                    >
                      <RefreshCw size={13} className={rescoringTriggering ? 'spin' : ''} />
                      {rescoringTriggering ? 'Simulating...' : 'Run Simulation'}
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Simulation History Table */}
            <div>
              <h4 style={{ fontSize: '0.9rem', color: '#f8fafc', marginBottom: 10 }}>Past Impact Simulations ({rescoreJobs.length})</h4>
              <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8rem' }}>
                    <thead>
                      <tr style={{ background: 'rgba(30, 41, 59, 0.7)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)' }}>
                        <th style={{ padding: '8px 12px', fontWeight: 600 }}>Job ID</th>
                        <th style={{ padding: '8px 12px', fontWeight: 600 }}>Status</th>
                        <th style={{ padding: '8px 12px', fontWeight: 600 }}>Items Evaluated</th>
                        <th style={{ padding: '8px 12px', fontWeight: 600 }}>Completed At</th>
                        <th style={{ padding: '8px 12px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rescoreJobs.length === 0 ? (
                        <tr>
                          <td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--text-dim)' }}>
                            No rescoring simulation batches executed yet.
                          </td>
                        </tr>
                      ) : (
                        rescoreJobs.map((j) => (
                          <tr key={j.id || j.job_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                            <td style={{ padding: '8px 12px', fontFamily: 'monospace', color: '#a5b4fc' }}>
                              {(j.id || j.job_id).substring(0, 18)}...
                            </td>
                            <td style={{ padding: '8px 12px' }}>
                              <span className={`badge ${j.status === 'completed' ? 'badge-success' : 'badge-neutral'}`}>
                                {j.status}
                              </span>
                            </td>
                            <td style={{ padding: '8px 12px', color: '#f8fafc' }}>
                              {j.completed_items || j.total_items || 0} / {j.total_items || 0}
                            </td>
                            <td style={{ padding: '8px 12px', color: 'var(--text-dim)' }}>
                              {j.completed_at ? new Date(j.completed_at).toLocaleString() : 'In Progress'}
                            </td>
                            <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                              <button
                                onClick={() => setSelectedRescoreJob(j)}
                                className="btn btn-secondary"
                                style={{ padding: '3px 8px', fontSize: '0.72rem' }}
                              >
                                View Impact
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Selected Job Drilldown */}
            {selectedRescoreJob && (
              <div className="card" style={{ marginTop: 16, background: 'rgba(0,0,0,0.2)' }}>
                <div className="flex-between" style={{ marginBottom: 10 }}>
                  <strong style={{ color: '#c084fc', fontSize: '0.88rem' }}>Simulation Summary Details</strong>
                  <button onClick={() => setSelectedRescoreJob(null)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '0.75rem' }}>
                    Dismiss
                  </button>
                </div>
                <div style={{ fontSize: '0.8rem', color: '#cbd5e1', lineHeight: 1.5 }}>
                  <div>Total items evaluated: <strong>{selectedRescoreJob.total_items}</strong></div>
                  <div>Status: <strong>{selectedRescoreJob.status}</strong></div>
                  {selectedRescoreJob.summary && (
                    <pre style={{ marginTop: 8, padding: 10, background: '#0b0f19', borderRadius: 6, fontSize: '0.75rem', overflowX: 'auto' }}>
                      {JSON.stringify(selectedRescoreJob.summary, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            )}

            <div style={{ marginTop: 20, textAlign: 'right' }}>
              <button onClick={() => setRescoreModalOpen(false)} className="btn btn-secondary">
                Close Hub
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Mandatory Excel Import Modal */}
      {excelModalOpen && (
        <ExcelImportModal
          isOpen={excelModalOpen}
          onClose={() => setExcelModalOpen(false)}
          onSuccess={() => loadData()}
        />
      )}

      {/* Mandatory Brand Profile Modal */}
      {brandProfileModalOpen && (
        <BrandProfileModal
          isOpen={brandProfileModalOpen}
          onClose={() => setBrandProfileModalOpen(false)}
          onSaved={() => loadData()}
        />
      )}
    </div>
  );
};
