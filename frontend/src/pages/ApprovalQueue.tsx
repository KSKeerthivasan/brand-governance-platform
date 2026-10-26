import React, { useEffect, useState } from 'react';
import {
  CheckSquare,
  CheckCircle,
  XCircle,
  RotateCcw,
  Clock,
  User,
  ShieldAlert,
  Hash,
  AlertTriangle
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { StatusBadge } from '../components/StatusBadge';
import { ApprovalSubmission } from '../types';

export const ApprovalQueue: React.FC = () => {
  const { user, role } = useAuth();
  const [submissions, setSubmissions] = useState<ApprovalSubmission[]>([]);
  const [selectedSub, setSelectedSub] = useState<ApprovalSubmission | null>(null);
  const [decisionNotes, setDecisionNotes] = useState('');
  const [deciding, setDeciding] = useState(false);
  const [loading, setLoading] = useState(true);

  const isApprover = role === 'approval_manager';

  const loadQueue = async () => {
    try {
      setLoading(true);
      const queue = await api.getApprovalQueue();
      setSubmissions(queue);
      if (queue.length > 0 && !selectedSub) {
        setSelectedSub(queue[0]);
      }
    } catch (err) {
      console.error('Failed to load approval queue:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const handleDecision = async (decision: 'approved' | 'rejected' | 'changes_requested') => {
    if (!selectedSub) return;
    if (!decisionNotes.trim()) {
      alert('Please provide decision comments explaining your review reasoning.');
      return;
    }

    setDeciding(true);
    try {
      await api.decideApproval(selectedSub.id, decision, decisionNotes);
      alert(`Decision recorded: ${decision === 'approved' ? 'Approved — Ready to Publish' : decision}`);
      setDecisionNotes('');
      await loadQueue();
      if (selectedSub) {
        const refreshed = await api.getApprovalQueue();
        const found = refreshed.find(s => s.id === selectedSub.id);
        setSelectedSub(found || refreshed[0] || null);
      }
    } catch (err: any) {
      alert(`Decision error: ${err.message}`);
    } finally {
      setDeciding(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 className="title-xl">Human Approval Queue</h1>
        <p className="text-sub">
          Authorized Approval Manager review. Formal decisions are permanently locked to the exact submitted version.
        </p>
      </div>

      {!isApprover && (
        <div style={{ padding: '12px 18px', background: 'rgba(99, 102, 241, 0.08)', borderRadius: 10, border: '1px solid rgba(99, 102, 241, 0.25)', marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
          <ShieldAlert size={20} color="#818cf8" />
          <div style={{ fontSize: '0.82rem', color: '#c7d2fe' }}>
            <strong>Viewing with role '{role}':</strong> Only the <strong>Approval Manager</strong> (Marcus Manager) has authority to approve content. Switch to Marcus Manager in the top-right persona menu to execute approval decisions.
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: 24, height: 'calc(100vh - 180px)' }}>
        {/* Left Column: Submissions List */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', padding: 16, overflowY: 'auto' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 14, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Pending Submissions ({submissions.length})
          </div>

          {loading ? (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-dim)' }}>Loading queue...</div>
          ) : submissions.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-dim)' }}>No submissions in queue.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, flex: 1, overflowY: 'auto' }}>
              {submissions.map((sub) => {
                const isSelected = selectedSub?.id === sub.id;
                return (
                  <div
                    key={sub.id}
                    onClick={() => setSelectedSub(sub)}
                    style={{
                      padding: 14,
                      borderRadius: 10,
                      background: isSelected ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                      border: isSelected ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ fontWeight: 700, fontSize: '0.9rem', color: isSelected ? '#fff' : 'var(--text-main)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {sub.content_item_title}
                      </div>
                      <StatusBadge status={sub.status} />
                    </div>

                    <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 6 }}>
                      Brand: <span style={{ color: 'var(--text-muted)' }}>{sub.brand_name}</span> | Version: <strong>v{sub.version_num}</strong>
                    </div>

                    <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <User size={12} /> Submitter: {sub.submitter_name || 'Creator'}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Submission Details & Decision Panel */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', padding: 24, overflowY: 'auto' }}>
          {!selectedSub ? (
            <div style={{ textAlign: 'center', padding: '100px 20px', color: 'var(--text-dim)' }}>
              Select a submission to review.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* Submission Header */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h2 className="title-lg">{selectedSub.content_item_title}</h2>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: 4 }}>
                      Brand: <strong>{selectedSub.brand_name}</strong> | Submitted by: <strong>{selectedSub.submitter_name}</strong> on {new Date(selectedSub.created_at).toLocaleString()}
                    </div>
                  </div>
                  <StatusBadge status={selectedSub.status} />
                </div>

                {/* Immutable Version Lock Pill */}
                <div style={{ marginTop: 14, padding: '10px 14px', background: 'rgba(0,0,0,0.3)', borderRadius: 8, border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Locked Submission Version: <strong>Version {selectedSub.version_num}</strong>
                  </div>
                  <div style={{ fontFamily: 'monospace', fontSize: '0.7rem', color: '#a5b4fc' }}>
                    sha256: {selectedSub.checksum}
                  </div>
                </div>

                {selectedSub.submission_notes && (
                  <div style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 6, fontSize: '0.8rem', color: '#cbd5e1' }}>
                    Creator Note: "{selectedSub.submission_notes}"
                  </div>
                )}
              </div>

              {/* Exact Submitted Body Text */}
              <div>
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Submitted Copy Text (Immutable)
                </div>
                <div style={{
                  padding: 16,
                  borderRadius: 10,
                  background: 'rgba(0,0,0,0.4)',
                  border: '1px solid var(--border-subtle)',
                  fontSize: '0.95rem',
                  lineHeight: 1.6,
                  color: '#fff',
                  whiteSpace: 'pre-wrap'
                }}>
                  {selectedSub.body_text}
                </div>
              </div>

              {/* Past Decisions History */}
              {selectedSub.decisions && selectedSub.decisions.length > 0 && (
                <div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Decision Audit History
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {selectedSub.decisions.map((dec) => (
                      <div key={dec.id} style={{ padding: '10px 14px', background: 'rgba(255,255,255,0.02)', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: dec.decision === 'approved' ? '#34d399' : '#fb7185' }}>
                            {dec.decision_label}
                          </span>
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                            {dec.decider_name || 'Approver'} • {new Date(dec.created_at).toLocaleString()}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>
                          "{dec.comments}"
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Approval Actions Panel */}
              <div style={{ marginTop: 'auto', paddingTop: 20, borderTop: '1px solid var(--border-subtle)' }}>
                {/* Conflict of interest warning */}
                {selectedSub.submitted_by === user?.id && (
                  <div style={{ padding: 10, borderRadius: 8, background: 'rgba(244,63,94,0.1)', border: '1px solid rgba(244,63,94,0.3)', color: '#fb7185', fontSize: '0.8rem', marginBottom: 14 }}>
                    <strong>Security Rule Enforced:</strong> You submitted this content. Creators cannot approve their own drafts. Switch to Marcus Manager (approver@freshsip.demo) to approve.
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">Approval Decision Comments (Required)</label>
                  <textarea
                    value={decisionNotes}
                    onChange={(e) => setDecisionNotes(e.target.value)}
                    className="textarea"
                    placeholder="Enter formal justification, compliance verification notes, or revision directions..."
                    style={{ minHeight: 70 }}
                    disabled={!isApprover}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
                  <button
                    onClick={() => handleDecision('changes_requested')}
                    disabled={!isApprover || deciding || selectedSub.submitted_by === user?.id}
                    className="btn btn-secondary"
                  >
                    <RotateCcw size={16} /> Request Changes
                  </button>
                  <button
                    onClick={() => handleDecision('rejected')}
                    disabled={!isApprover || deciding || selectedSub.submitted_by === user?.id}
                    className="btn btn-danger"
                  >
                    <XCircle size={16} /> Reject
                  </button>
                  <button
                    onClick={() => handleDecision('approved')}
                    disabled={!isApprover || deciding || selectedSub.submitted_by === user?.id}
                    className="btn btn-success"
                  >
                    <CheckCircle size={16} /> Approve — Ready to Publish
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
