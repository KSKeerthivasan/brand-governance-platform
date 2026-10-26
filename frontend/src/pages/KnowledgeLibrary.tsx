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
  Tag
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { StatusBadge } from '../components/StatusBadge';
import { KnowledgeRule, KnowledgeFact, KnowledgeSource, BrandAsset, Brand } from '../types';

export const KnowledgeLibrary: React.FC = () => {
  const { role } = useAuth();
  const [activeTab, setActiveTab] = useState<'rules' | 'facts' | 'assets' | 'sources'>('rules');
  const [rules, setRules] = useState<KnowledgeRule[]>([]);
  const [facts, setFacts] = useState<KnowledgeFact[]>([]);
  const [assets, setAssets] = useState<BrandAsset[]>([]);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);

  // Upload modal state
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadType, setUploadType] = useState('pdf_brand_guidelines');
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Filter state
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const isReviewer = role === 'knowledge_reviewer' || role === 'org_admin';

  const loadData = async () => {
    try {
      setLoading(true);
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
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !uploadTitle) {
      alert('Please provide a document title and file.');
      return;
    }

    setUploading(true);
    setUploadMsg(null);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('title', uploadTitle);
      formData.append('source_type', uploadType);
      if (selectedBrandId) formData.append('brand_id', selectedBrandId);

      const createdSource = await api.uploadKnowledge(formData);
      setUploadMsg({
        type: 'success',
        text: `Uploaded '${createdSource.title}'. ${createdSource.rules_count || 0} candidate rules and ${createdSource.facts_count || 0} facts extracted into Pending Review.`
      });
      setUploadFile(null);
      setUploadTitle('');
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

  const handleReviewAsset = async (assetId: string, status: 'approved' | 'rejected') => {
    try {
      await api.reviewAsset(assetId, status);
      await loadData();
    } catch (err: any) {
      alert(`Review error: ${err.message}`);
    }
  };

  const filteredRules = rules.filter(r => statusFilter === 'all' || r.status === statusFilter);
  const filteredFacts = facts.filter(f => statusFilter === 'all' || f.status === statusFilter);
  const filteredAssets = assets.filter(a => statusFilter === 'all' || a.status === statusFilter);

  return (
    <div>
      {/* Header */}
      <div className="flex-between" style={{ marginBottom: 24 }}>
        <div>
          <h1 className="title-xl">Knowledge Library & Human Review</h1>
          <p className="text-sub">
            Brand guidelines, approved product facts, and creative assets. Only <strong>Approved</strong> records are authoritative.
          </p>
        </div>
        <button onClick={() => setUploadModalOpen(true)} className="btn btn-primary">
          <Upload size={16} /> Upload Guidelines or Assets
        </button>
      </div>

      {/* Pending Knowledge Notice */}
      <div style={{ padding: '12px 18px', background: 'rgba(245, 158, 11, 0.08)', borderRadius: 10, border: '1px solid rgba(245, 158, 11, 0.25)', marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
        <AlertCircle size={20} color="#fbbf24" />
        <div style={{ fontSize: '0.82rem', color: '#fef3c7' }}>
          <strong>Core Governance Principle:</strong> Newly uploaded documents and extracted rules start in a <strong>pending review</strong> state. Uploading never auto-approves knowledge. Knowledge Reviewers must approve candidate facts before the governance engine uses them.
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

        {/* Status Filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {filteredRules.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-dim)' }}>
              No rules found for filter '{statusFilter}'.
            </div>
          ) : (
            filteredRules.map((rule) => (
              <div key={rule.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontWeight: 700, fontSize: '0.95rem', color: '#fff' }}>{rule.title}</span>
                    <StatusBadge status={rule.status} />
                    <span className={`badge badge-${rule.severity === 'critical' ? 'danger' : 'warning'}`}>
                      {rule.severity}
                    </span>
                    <span className="badge badge-neutral">
                      {rule.rule_type.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <div style={{ marginTop: 8, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    {rule.explanation}
                  </div>
                  <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                    <div>Pattern: <code style={{ color: '#a5b4fc', background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: 4 }}>{rule.pattern}</code></div>
                    <div>Source: <span style={{ color: 'var(--text-muted)' }}>{rule.source_citation || 'Brand Guidelines'}</span></div>
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {filteredFacts.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-dim)' }}>
              No product facts found for filter '{statusFilter}'.
            </div>
          ) : (
            filteredFacts.map((fact) => (
              <div key={fact.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontWeight: 700, fontSize: '0.95rem', color: '#fff' }}>
                      {fact.product_name} — {fact.fact_key}
                    </span>
                    <StatusBadge status={fact.status} />
                    <span className="badge badge-info">{fact.category}</span>
                  </div>
                  <div style={{ marginTop: 8, fontSize: '0.9rem', color: '#e2e8f0', fontWeight: 600 }}>
                    Verified Specification: <span style={{ color: '#34d399' }}>"{fact.fact_value}"</span>
                  </div>
                  <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                    <div>Source Citation: <span style={{ color: 'var(--text-muted)' }}>{fact.source_citation || 'Product Knowledge Spec'}</span></div>
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
        <div className="grid-3">
          {filteredAssets.length === 0 ? (
            <div className="card" style={{ gridColumn: 'span 3', textAlign: 'center', padding: 40, color: 'var(--text-dim)' }}>
              No brand assets found.
            </div>
          ) : (
            filteredAssets.map((asset) => (
              <div key={asset.id} className="card">
                <div className="flex-between">
                  <span className="badge badge-neutral">{asset.asset_type.replace(/_/g, ' ')}</span>
                  <StatusBadge status={asset.status} />
                </div>
                <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.95rem', marginTop: 12 }}>
                  {asset.asset_name}
                </div>
                <div style={{ marginTop: 8, fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div>Dimensions: <strong>{asset.width}x{asset.height}px</strong> ({asset.aspect_ratio})</div>
                  <div>Color Mode: <strong>{asset.color_mode || 'RGB'}</strong></div>
                  <div>Clearance Perimeter: <strong>{asset.min_clearance_px || 20}px</strong></div>
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {sources.map((src) => (
            <div key={src.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <FileText size={18} color="#818cf8" />
                  <span style={{ fontWeight: 700, fontSize: '0.95rem', color: '#fff' }}>{src.title}</span>
                  <StatusBadge status={src.status} />
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
                  Filename: {src.filename} | Size: {(src.file_size_bytes / 1024).toFixed(1)} KB | Uploaded: {new Date(src.created_at).toLocaleDateString()}
                </div>
                {src.extracted_summary && (
                  <div style={{ marginTop: 6, fontSize: '0.8rem', color: '#a5b4fc' }}>
                    {src.extracted_summary}
                  </div>
                )}
              </div>
              <div style={{ textAlign: 'right', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                <div>Rules Extracted: <strong>{src.rules_count || 0}</strong></div>
                <div>Facts Extracted: <strong>{src.facts_count || 0}</strong></div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload Modal */}
      {uploadModalOpen && (
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
          <div className="card" style={{ width: 480, background: '#131b2e', border: '1px solid rgba(255,255,255,0.15)' }}>
            <div className="flex-between" style={{ marginBottom: 16 }}>
              <h2 className="title-md">Upload Brand Knowledge or Assets</h2>
              <button onClick={() => setUploadModalOpen(false)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleUpload}>
              <div className="form-group">
                <label className="form-label">Document Title</label>
                <input
                  type="text"
                  placeholder="e.g. Freshsip Brand Guidelines Q4"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  className="input"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Knowledge Category</label>
                <select
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value)}
                  className="select"
                >
                  <option value="pdf_brand_guidelines">PDF Brand Guidelines</option>
                  <option value="pdf_product_knowledge">PDF Product Knowledge & Specs</option>
                  <option value="supporting_doc">Supporting Evidence Document</option>
                  <option value="brand_asset_image">Brand Asset / Creative Image</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Brand</label>
                <select
                  value={selectedBrandId}
                  onChange={(e) => setSelectedBrandId(e.target.value)}
                  className="select"
                >
                  {brands.map(b => (
                    <option key={b.id} value={b.id}>{b.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Select File (PDF, PNG, JPG, WEBP)</label>
                <input
                  type="file"
                  accept=".pdf,image/png,image/jpeg,image/webp,image/svg+xml"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="input"
                  required
                />
              </div>

              {uploadMsg && (
                <div style={{
                  padding: 10,
                  borderRadius: 6,
                  fontSize: '0.8rem',
                  marginBottom: 14,
                  background: uploadMsg.type === 'success' ? 'rgba(16,185,129,0.15)' : 'rgba(244,63,94,0.15)',
                  color: uploadMsg.type === 'success' ? '#34d399' : '#fb7185'
                }}>
                  {uploadMsg.text}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
                <button type="button" onClick={() => setUploadModalOpen(false)} className="btn btn-secondary">
                  Close
                </button>
                <button type="submit" disabled={uploading} className="btn btn-primary">
                  {uploading ? 'Processing Extraction...' : 'Upload & Extract Candidates'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
