import React, { useState, useEffect } from 'react';
import { MessageSquare, AlertCircle, CheckCircle, ShieldAlert, X, History, User } from 'lucide-react';
import { api } from '../services/api';
import { GovernanceFinding, ReviewerFindingDisposition } from '../types';

interface FindingFeedbackModalProps {
  finding: GovernanceFinding | null;
  isOpen: boolean;
  onClose: () => void;
  canReview: boolean;
  onDispositionRecorded?: (disposition: ReviewerFindingDisposition) => void;
}

const DISPOSITION_OPTIONS = [
  { value: 'confirmed_issue', label: 'Confirmed Issue (Accurate Violation)', requiresJustification: false },
  { value: 'false_positive', label: 'False Positive (Compliant Content Over-flagged)', requiresJustification: true },
  { value: 'guideline_unclear', label: 'Guideline Unclear (Vague or Ambiguous)', requiresJustification: true },
  { value: 'conflicting_guidelines', label: 'Conflicting Guidelines (Contradicts Another Rule)', requiresJustification: true },
  { value: 'insufficient_evidence', label: 'Insufficient Evidence (Citation or Context Lacking)', requiresJustification: true },
  { value: 'other', label: 'Other Reviewer Observation', requiresJustification: false },
];

export const FindingFeedbackModal: React.FC<FindingFeedbackModalProps> = ({
  finding,
  isOpen,
  onClose,
  canReview,
  onDispositionRecorded
}) => {
  const [disposition, setDisposition] = useState<string>('confirmed_issue');
  const [explanation, setExplanation] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [history, setHistory] = useState<ReviewerFindingDisposition[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    if (isOpen && finding) {
      setDisposition('confirmed_issue');
      setExplanation('');
      setError(null);
      setSuccess(null);
      fetchHistory(finding.id);
    }
  }, [isOpen, finding]);

  const fetchHistory = async (findingId: string) => {
    try {
      setLoadingHistory(true);
      const data = await api.getFindingDispositions(findingId);
      setHistory(data);
    } catch (err) {
      console.error('Failed to load finding dispositions history:', err);
    } finally {
      setLoadingHistory(false);
    }
  };

  if (!isOpen || !finding) return null;

  const currentOption = DISPOSITION_OPTIONS.find(o => o.value === disposition);
  const requiresJustification = currentOption?.requiresJustification ?? false;
  const isExplanationValid = !requiresJustification || (explanation.trim().length >= 10);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (requiresJustification && explanation.trim().length < 10) {
      setError(`Explanation Required: Dispositions that question or challenge a rule ('${disposition}') require at least 10 characters of justification.`);
      return;
    }

    try {
      setSubmitting(true);
      const result = await api.submitFindingDisposition(finding.id, disposition, explanation.trim());
      setSuccess(`Disposition '${disposition}' successfully recorded into auditable history.`);
      setHistory(prev => [result, ...prev]);
      setExplanation('');
      if (onDispositionRecorded) {
        onDispositionRecorded(result);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to record finding disposition.');
    } finally {
      setSubmitting(false);
    }
  };

  const getBadgeColor = (disp: string) => {
    switch (disp) {
      case 'confirmed_issue':
        return { bg: 'rgba(239, 68, 68, 0.2)', text: '#fca5a5', border: 'rgba(239, 68, 68, 0.4)' };
      case 'false_positive':
        return { bg: 'rgba(245, 158, 11, 0.2)', text: '#fde68a', border: 'rgba(245, 158, 11, 0.4)' };
      case 'guideline_unclear':
      case 'conflicting_guidelines':
        return { bg: 'rgba(168, 85, 247, 0.2)', text: '#d8b4fe', border: 'rgba(168, 85, 247, 0.4)' };
      case 'insufficient_evidence':
        return { bg: 'rgba(59, 130, 246, 0.2)', text: '#93c5fd', border: 'rgba(59, 130, 246, 0.4)' };
      default:
        return { bg: 'rgba(148, 163, 184, 0.2)', text: '#cbd5e1', border: 'rgba(148, 163, 184, 0.4)' };
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      backdropFilter: 'blur(4px)',
      padding: 20
    }}>
      <div style={{
        background: '#0f172a',
        border: '1px solid var(--border-subtle)',
        borderRadius: 14,
        width: '100%',
        maxWidth: 620,
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
        overflow: 'hidden'
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'rgba(255,255,255,0.02)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: 'rgba(99, 102, 241, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#818cf8'
            }}>
              <MessageSquare size={16} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#fff' }}>
                Reviewer Finding Disposition & Ambiguity Feedback
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                Milestone 5B Evidence Feedback for Knowledge Managers
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-dim)',
              cursor: 'pointer',
              padding: 4
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Content body */}
        <div style={{ padding: 20, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Finding summary card */}
          <div style={{
            padding: 12,
            background: 'rgba(255,255,255,0.03)',
            borderRadius: 8,
            border: '1px solid var(--border-subtle)'
          }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>
              Target Governance Finding
            </div>
            <div style={{ fontWeight: 700, color: '#e2e8f0', fontSize: '0.9rem', marginTop: 4 }}>
              {finding.matched_rule_code ? `[${finding.matched_rule_code}] ` : ''}{finding.title}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.4 }}>
              {finding.explanation}
            </div>
            {finding.text_excerpt && (
              <div style={{ fontSize: '0.74rem', color: '#cbd5e1', background: 'rgba(0,0,0,0.3)', padding: '4px 8px', borderRadius: 4, marginTop: 6, fontFamily: 'monospace' }}>
                Violation excerpt: "{finding.text_excerpt}"
              </div>
            )}
            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 6, display: 'flex', gap: 10 }}>
              <span>Rule ID: <code>{finding.matched_rule_id ? finding.matched_rule_id.substring(0, 8) + '...' : 'N/A'}</code></span>
              <span>Citation: <strong style={{ color: '#cbd5e1' }}>{finding.source_citation || 'Brand Guidelines'}</strong></span>
            </div>
          </div>

          {/* Alert messages */}
          {error && (
            <div style={{
              padding: '10px 14px',
              borderRadius: 8,
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#fca5a5',
              fontSize: '0.8rem',
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div style={{
              padding: '10px 14px',
              borderRadius: 8,
              background: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: '#6ee7b7',
              fontSize: '0.8rem',
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}>
              <CheckCircle size={16} />
              <span>{success}</span>
            </div>
          )}

          {/* Feedback Form (Only for authorized reviewers) */}
          {canReview ? (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>
                  Reviewer Disposition Category
                </label>
                <select
                  value={disposition}
                  onChange={(e) => setDisposition(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: 8,
                    background: '#1e293b',
                    border: '1px solid var(--border-subtle)',
                    color: '#fff',
                    fontSize: '0.85rem'
                  }}
                >
                  {DISPOSITION_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label} {opt.requiresJustification ? '(Explanation required)' : ''}
                    </option>
                  ))}
                </select>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 4 }}>
                  {requiresJustification
                    ? 'Dispositions that question a rule require a meaningful explanation to guide Knowledge Base improvements.'
                    : 'Records confirmation that the finding was a legitimate violation of brand rules.'}
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>
                  Reviewer Explanation & Evidence Note
                  {requiresJustification && (
                    <span style={{ color: explanation.trim().length >= 10 ? '#34d399' : '#f87171', marginLeft: 6 }}>
                      ({explanation.trim().length}/10 chars min)
                    </span>
                  )}
                </label>
                <textarea
                  value={explanation}
                  onChange={(e) => setExplanation(e.target.value)}
                  placeholder={
                    requiresJustification
                      ? "Explain why the rule was ambiguous, conflicting, or produced a false positive (min 10 characters)..."
                      : "Optional reviewer notes or context..."
                  }
                  rows={3}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: 8,
                    background: '#1e293b',
                    border: requiresJustification && explanation.trim().length > 0 && explanation.trim().length < 10
                      ? '1px solid #f87171'
                      : '1px solid var(--border-subtle)',
                    color: '#fff',
                    fontSize: '0.82rem',
                    resize: 'vertical'
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button
                  type="button"
                  onClick={onClose}
                  className="btn btn-secondary"
                  style={{ padding: '8px 14px', fontSize: '0.8rem' }}
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={submitting || (requiresJustification && explanation.trim().length < 10)}
                  className="btn btn-primary"
                  style={{ padding: '8px 16px', fontSize: '0.8rem', opacity: (requiresJustification && explanation.trim().length < 10) ? 0.6 : 1 }}
                >
                  {submitting ? 'Recording...' : 'Record Disposition'}
                </button>
              </div>
            </form>
          ) : (
            <div style={{
              padding: 12,
              borderRadius: 8,
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid var(--border-subtle)',
              fontSize: '0.78rem',
              color: 'var(--text-dim)',
              textAlign: 'center'
            }}>
              Only Approval Managers, Knowledge Reviewers, and Org Admins can record reviewer dispositions.
            </div>
          )}

          {/* Historical Dispositions for this finding */}
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6, textTransform: 'uppercase' }}>
              <History size={14} /> Recorded Audit History ({history.length})
            </div>

            {loadingHistory ? (
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textAlign: 'center', padding: 12 }}>
                Loading disposition history...
              </div>
            ) : history.length === 0 ? (
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textAlign: 'center', padding: 12, background: 'rgba(255,255,255,0.01)', borderRadius: 6 }}>
                No dispositions recorded yet for this finding.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 180, overflowY: 'auto' }}>
                {history.map((disp) => {
                  const badge = getBadgeColor(disp.disposition);
                  return (
                    <div
                      key={disp.id}
                      style={{
                        padding: '8px 12px',
                        borderRadius: 6,
                        background: 'rgba(255,255,255,0.02)',
                        border: '1px solid var(--border-subtle)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 4
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{
                          fontSize: '0.7rem',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 4,
                          background: badge.bg,
                          color: badge.text,
                          border: `1px solid ${badge.border}`
                        }}>
                          {disp.disposition.replace(/_/g, ' ').toUpperCase()}
                        </span>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
                          {disp.reviewer_name || 'Reviewer'} • {new Date(disp.created_at).toLocaleString()}
                        </span>
                      </div>
                      {disp.explanation && (
                        <div style={{ fontSize: '0.78rem', color: '#cbd5e1', fontStyle: 'italic', marginTop: 2 }}>
                          "{disp.explanation}"
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
