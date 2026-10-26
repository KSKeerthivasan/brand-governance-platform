import React, { useState, useEffect } from 'react';
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
  Plus
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { StatusBadge } from '../components/StatusBadge';
import { ContentItem, ContentVersion, GovernanceRun, Brand } from '../types';

export const ContentStudio: React.FC = () => {
  const { role } = useAuth();
  const [contentList, setContentList] = useState<ContentItem[]>([]);
  const [selectedContent, setSelectedContent] = useState<ContentItem | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [versions, setVersions] = useState<ContentVersion[]>([]);
  const [latestGovRun, setLatestGovRun] = useState<GovernanceRun | null>(null);

  // Form Editor State
  const [title, setTitle] = useState('');
  const [channel, setChannel] = useState('Social Media');
  const [bodyText, setBodyText] = useState('');
  const [selectedBrandId, setSelectedBrandId] = useState('');

  // Status & Loading
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submitModalOpen, setSubmitModalOpen] = useState(false);
  const [submitNotes, setSubmitNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const isCreator = role === 'content_creator' || role === 'org_admin';

  const loadContents = async () => {
    try {
      const [items, b] = await Promise.all([
        api.getContentItems(),
        api.getBrands()
      ]);
      setContentList(items);
      setBrands(b);
      if (b.length > 0 && !selectedBrandId) {
        setSelectedBrandId(b[0].id);
      }
      if (items.length > 0 && !selectedContent) {
        selectDraft(items[0]);
      }
    } catch (err) {
      console.error('Failed to load content items:', err);
    }
  };

  useEffect(() => {
    loadContents();
  }, []);

  const selectDraft = async (item: ContentItem) => {
    setSelectedContent(item);
    setTitle(item.title);
    setChannel(item.channel);
    setSelectedBrandId(item.brand_id);
    setBodyText(item.latest_version?.body_text || '');

    // Load versions
    try {
      const vers = await api.getContentVersions(item.id);
      setVersions(vers);

      // Load latest governance run for the current version
      if (item.latest_version) {
        try {
          const run = await api.getLatestGovernanceRun(item.latest_version.id);
          setLatestGovRun(run);
        } catch {
          setLatestGovRun(null);
        }
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
    setLatestGovRun(null);
    setVersions([]);
  };

  const handleSaveDraft = async () => {
    if (!title || !bodyText) {
      alert('Please provide title and content text.');
      return;
    }
    setSaving(true);
    try {
      if (selectedContent) {
        const updated = await api.updateContentItem(selectedContent.id, bodyText, title, channel);
        await selectDraft(updated);
        await loadContents();
      } else {
        const created = await api.createContentItem(selectedBrandId, title, channel, bodyText);
        await loadContents();
        await selectDraft(created);
      }
    } catch (err: any) {
      alert(`Save error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleRunChecks = async () => {
    if (!selectedContent?.latest_version) {
      // Save first
      await handleSaveDraft();
    }
    if (!selectedContent?.latest_version) return;

    setChecking(true);
    try {
      const run = await api.runGovernanceCheck(selectedContent.latest_version.id);
      setLatestGovRun(run);
    } catch (err: any) {
      alert(`Governance check error: ${err.message}`);
    } finally {
      setChecking(false);
    }
  };

  const handleSubmitForApproval = async () => {
    if (!selectedContent?.latest_version) return;
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

  return (
    <div>
      {/* Studio Header */}
      <div className="flex-between" style={{ marginBottom: 20 }}>
        <div>
          <h1 className="title-xl">Content Studio & Governance Findings</h1>
          <p className="text-sub">
            Author marketing copy, run deterministic checks, inspect explainable citations, and submit versions.
          </p>
        </div>
        <button onClick={handleCreateNewDraft} className="btn btn-secondary">
          <Plus size={16} /> New Draft
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr 400px', gap: 20, height: 'calc(100vh - 170px)' }}>
        {/* Left Column: Drafts & Revisions List */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', padding: 14, overflowY: 'auto' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Drafts & Submissions
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, overflowY: 'auto' }}>
            {contentList.map((item) => {
              const isSelected = selectedContent?.id === item.id;
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
                    <div style={{ fontWeight: 600, fontSize: '0.875rem', color: isSelected ? '#fff' : 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 170 }}>
                      {item.title}
                    </div>
                    <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: 4, background: 'rgba(255,255,255,0.08)', color: '#cbd5e1' }}>
                      v{item.current_version_num}
                    </span>
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
                      <span>Version {ver.version_num}</span>
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

        {/* Center Column: Marketing Text Editor */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', padding: 20 }}>
          <div style={{ display: 'flex', gap: 14, marginBottom: 16 }}>
            <div style={{ flex: 1 }}>
              <label className="form-label">Draft Title</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="input"
                placeholder="Campaign / Social post headline"
              />
            </div>
            <div style={{ width: 160 }}>
              <label className="form-label">Target Channel</label>
              <select
                value={channel}
                onChange={(e) => setChannel(e.target.value)}
                className="select"
              >
                <option value="Social Media">Social Media</option>
                <option value="Email Newsletter">Email Newsletter</option>
                <option value="Website Banner">Website Banner</option>
                <option value="Print Ad">Print Ad</option>
              </select>
            </div>
          </div>

          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', marginBottom: 16 }}>
            <div className="flex-between" style={{ marginBottom: 6 }}>
              <label className="form-label">Marketing Copy Text</label>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                {bodyText.length} characters | Editing creates an immutable version
              </span>
            </div>
            <textarea
              value={bodyText}
              onChange={(e) => setBodyText(e.target.value)}
              className="textarea"
              placeholder="Draft your promotional text here. The governance engine will evaluate this against approved brand rules and product knowledge facts..."
              style={{ flex: 1, minHeight: 280, fontSize: '0.95rem', lineHeight: 1.6 }}
            />
          </div>

          {/* Action Bar */}
          <div className="flex-between" style={{ paddingTop: 14, borderTop: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {selectedContent && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                  Current Version: <strong>v{selectedContent.current_version_num}</strong> | Status: <StatusBadge status={selectedContent.status} />
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={handleSaveDraft} disabled={saving} className="btn btn-secondary">
                {saving ? 'Saving...' : 'Save Draft Revision'}
              </button>
              <button onClick={handleRunChecks} disabled={checking} className="btn btn-primary">
                <Play size={16} /> {checking ? 'Evaluating Rules...' : 'Run Governance Check'}
              </button>
              {selectedContent && isCreator && selectedContent.status !== 'approved' && (
                <button
                  onClick={() => setSubmitModalOpen(true)}
                  className="btn btn-success"
                >
                  <Send size={16} /> Submit for Approval
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Explainable Governance Findings */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', padding: 18, overflowY: 'auto' }}>
          <div className="flex-between" style={{ marginBottom: 14 }}>
            <h2 className="title-md" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={18} color="#818cf8" /> Governance Engine
            </h2>
            {latestGovRun && (
              <span className={`badge badge-${latestGovRun.overall_status === 'passed' ? 'success' : (latestGovRun.overall_status === 'warnings' ? 'warning' : 'danger')}`}>
                {latestGovRun.overall_status.toUpperCase()}
              </span>
            )}
          </div>

          {!latestGovRun ? (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-dim)' }}>
              <ShieldAlert size={36} style={{ margin: '0 auto 12px auto', opacity: 0.4 }} />
              <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>No Check Executed Yet</div>
              <div style={{ fontSize: '0.78rem', marginTop: 4 }}>
                Click "Run Governance Check" to evaluate this text against approved organizational rules & facts.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
              {/* Summary Stats */}
              <div style={{ display: 'flex', gap: 8, padding: 10, background: 'rgba(255,255,255,0.02)', borderRadius: 8, border: '1px solid var(--border-subtle)', fontSize: '0.75rem' }}>
                <div style={{ flex: 1, textAlign: 'center' }}>
                  <div style={{ color: 'var(--text-dim)' }}>Rules Evaluated</div>
                  <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.9rem' }}>{latestGovRun.rules_evaluated_count}</div>
                </div>
                <div style={{ flex: 1, textAlign: 'center', borderLeft: '1px solid var(--border-subtle)' }}>
                  <div style={{ color: 'var(--text-dim)' }}>Facts Checked</div>
                  <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.9rem' }}>{latestGovRun.facts_evaluated_count}</div>
                </div>
                <div style={{ flex: 1, textAlign: 'center', borderLeft: '1px solid var(--border-subtle)' }}>
                  <div style={{ color: 'var(--text-dim)' }}>Findings</div>
                  <div style={{ fontWeight: 700, color: latestGovRun.findings_count > 0 ? '#fb7185' : '#34d399', fontSize: '0.9rem' }}>
                    {latestGovRun.findings_count}
                  </div>
                </div>
              </div>

              {latestGovRun.findings_count === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px 10px', background: 'rgba(16,185,129,0.08)', borderRadius: 10, border: '1px solid rgba(16,185,129,0.2)' }}>
                  <CheckCircle size={32} color="#34d399" style={{ margin: '0 auto 8px auto' }} />
                  <div style={{ fontWeight: 700, color: '#34d399', fontSize: '0.95rem' }}>All Governance Checks Passed</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
                    Content adheres to all approved brand rules and product knowledge facts.
                  </div>
                </div>
              ) : (
                latestGovRun.findings.map((f, idx) => (
                  <div
                    key={f.id || idx}
                    style={{
                      padding: 12,
                      borderRadius: 10,
                      background: f.severity === 'critical' ? 'rgba(244,63,94,0.08)' : 'rgba(245,158,11,0.08)',
                      border: f.severity === 'critical' ? '1px solid rgba(244,63,94,0.25)' : '1px solid rgba(245,158,11,0.25)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 6
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.85rem', color: f.severity === 'critical' ? '#fb7185' : '#fbbf24' }}>
                        {f.title}
                      </span>
                      <span className={`badge badge-${f.severity === 'critical' ? 'danger' : 'warning'}`}>
                        {f.severity}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.8rem', color: '#e2e8f0' }}>
                      {f.explanation}
                    </div>

                    {f.text_excerpt && (
                      <div style={{ padding: '4px 8px', background: 'rgba(0,0,0,0.3)', borderRadius: 4, fontFamily: 'monospace', fontSize: '0.72rem', color: '#cbd5e1' }}>
                        Excerpt: "{f.text_excerpt}"
                      </div>
                    )}

                    {/* Source Citation with explicit handling */}
                    <div style={{ fontSize: '0.72rem', marginTop: 4, paddingTop: 4, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                      <div style={{ color: 'var(--text-dim)' }}>
                        Source Citation: <strong style={{ color: f.source_citation === 'SUPPORTING EVIDENCE NOT FOUND' ? '#fb7185' : '#818cf8' }}>
                          {f.source_citation}
                        </strong>
                      </div>
                      <div style={{ color: '#34d399', marginTop: 4 }}>
                        Action: {f.recommended_action}
                      </div>
                    </div>
                  </div>
                ))
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
          <div className="card" style={{ width: 440, background: '#131b2e', border: '1px solid rgba(255,255,255,0.15)' }}>
            <h2 className="title-md" style={{ marginBottom: 12 }}>
              Submit for Human Approval
            </h2>
            <p className="text-sub" style={{ marginBottom: 14 }}>
              This will lock <strong>Version {selectedContent?.current_version_num}</strong> with immutable checksum:
              <br />
              <code style={{ fontSize: '0.7rem', color: '#a5b4fc' }}>
                {selectedContent?.latest_version?.checksum.slice(0, 24)}...
              </code>
            </p>

            <div className="form-group">
              <label className="form-label">Submission Notes for Approval Manager</label>
              <textarea
                value={submitNotes}
                onChange={(e) => setSubmitNotes(e.target.value)}
                className="textarea"
                placeholder="e.g., Reviewed against Q4 guidelines. All medical claims removed."
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
    </div>
  );
};
