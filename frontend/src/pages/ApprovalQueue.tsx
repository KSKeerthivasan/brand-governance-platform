import React, { useEffect, useState } from 'react';
import {
  CheckSquare,
  CheckCircle,
  XCircle,
  RotateCcw,
  Clock,
  User,
  ShieldAlert,
  ShieldCheck,
  Hash,
  AlertTriangle,
  AlertOctagon,
  Image as ImageIcon,
  Sparkles,
  Info,
  FileText,
  Lock,
  Layers,
  Search,
  MessageSquare
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { StatusBadge } from '../components/StatusBadge';
import { ApprovalSubmission, GovernanceRun, GovernanceFinding } from '../types';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import { FindingFeedbackModal } from '../components/FindingFeedbackModal';

export const ApprovalQueue: React.FC = () => {
  const { user, role } = useAuth();
  const [submissions, setSubmissions] = useState<ApprovalSubmission[]>([]);
  const [selectedSub, setSelectedSub] = useState<ApprovalSubmission | null>(null);
  const [latestGovRun, setLatestGovRun] = useState<GovernanceRun | null>(null);
  const [decisionNotes, setDecisionNotes] = useState('');
  const [deciding, setDeciding] = useState(false);
  const [loading, setLoading] = useState(true);
  const [selectedFindingForFeedback, setSelectedFindingForFeedback] = useState<GovernanceFinding | null>(null);
  const [selectedPdfPage, setSelectedPdfPage] = useState<number>(1);

  const isApprover = role === 'approval_manager';

  const loadQueue = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const queue = await api.getApprovalQueue();
      setSubmissions(queue);
      setSelectedSub(prev => {
        if (!prev) return queue.length > 0 ? queue[0] : null;
        const updated = queue.find(s => s.id === prev.id);
        return updated || prev;
      });
    } catch (err) {
      console.error('Failed to load approval queue:', err);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue(false);
  }, []);

  useEffect(() => {
    setSelectedPdfPage(1);
    if (selectedSub?.content_version_id) {
      api.getLatestGovernanceRun(selectedSub.content_version_id)
        .then(setLatestGovRun)
        .catch(() => setLatestGovRun(null));
    } else {
      setLatestGovRun(null);
    }
  }, [selectedSub?.content_version_id]);

  useAutoRefresh(() => {
    if (!deciding) {
      loadQueue(true);
    }
  }, { intervalMs: 6000 });

  // Consolidate findings from submission or latest run
  const activeFindings: GovernanceFinding[] =
    (selectedSub?.findings && selectedSub.findings.length > 0)
      ? selectedSub.findings
      : (latestGovRun?.findings || []);

  const criticalBlockers = activeFindings.filter(
    f => f.severity === 'critical' || f.severity === 'high' || f.is_blocker
  );
  const warnings = activeFindings.filter(
    f => f.severity === 'warning' && !f.is_blocker
  );
  const infoFindings = activeFindings.filter(
    f => f.severity === 'info' && !f.is_blocker
  );

  const hasCriticalBlockers = criticalBlockers.length > 0 || (selectedSub?.critical_findings_count ?? 0) > 0;
  const hasWarningsOnly = !hasCriticalBlockers && (warnings.length > 0 || (selectedSub?.warning_findings_count ?? 0) > 0);
  const isSelfSubmission = selectedSub ? selectedSub.submitted_by === user?.id : false;

  const handleDecision = async (decision: 'approved' | 'rejected' | 'changes_requested') => {
    if (!selectedSub) return;

    if (decision === 'approved' && hasCriticalBlockers) {
      alert('Policy Gate Error: Unresolved critical policy violations exist for this content version. Critical violations cannot be approved under any override.');
      return;
    }

    if (decision === 'approved' && hasWarningsOnly && decisionNotes.trim().length < 10) {
      alert('Warning Override Policy: Content contains active warnings. Approving requires entering a substantive justification in the comments (at least 10 characters).');
      return;
    }

    if ((decision === 'rejected' || decision === 'changes_requested') && !decisionNotes.trim()) {
      alert('Please provide decision comments explaining your review reasoning and specific revision instructions.');
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
      <div style={{ marginBottom: 20 }}>
        <h1 className="title-xl">Human Approval Queue</h1>
        <p className="text-sub">
          Authorized Approval Manager review. Formal decisions lock both advertisement copy and creative posters to the exact submitted version. Fail-closed policy prevents approving critical violations.
        </p>
      </div>

      {!isApprover && (
        <div style={{ padding: '12px 18px', background: 'rgba(99, 102, 241, 0.08)', borderRadius: 10, border: '1px solid rgba(99, 102, 241, 0.25)', marginBottom: 20, display: 'flex', alignItems: 'center', gap: 12 }}>
          <ShieldAlert size={20} color="#818cf8" />
          <div style={{ fontSize: '0.82rem', color: '#c7d2fe' }}>
            <strong>Viewing with role '{role}':</strong> Only the <strong>Approval Manager</strong> (Marcus Manager) has authority to approve content. Switch to Marcus Manager in the top-right persona menu to execute approval decisions.
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: 20, minHeight: 'calc(100vh - 180px)' }}>
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
                const hasPoster = Boolean(sub.poster_file_path);
                const subHasBlockers = (sub.critical_findings_count ?? 0) > 0;
                const subHasWarnings = (sub.warning_findings_count ?? 0) > 0;

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
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                      <div style={{ fontWeight: 700, fontSize: '0.9rem', color: isSelected ? '#fff' : 'var(--text-main)', maxWidth: 190, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {sub.content_item_title}
                      </div>
                      <StatusBadge status={sub.status} />
                    </div>

                    <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 6, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <span>Brand: <strong style={{ color: 'var(--text-muted)' }}>{sub.brand_name}</strong></span>
                      <span>•</span>
                      <span>v{sub.version_num}</span>
                      {sub.channel && (
                        <>
                          <span>•</span>
                          <span style={{ color: '#cbd5e1' }}>{sub.channel}</span>
                        </>
                      )}
                      {hasPoster && (
                        <span title="Poster attached" style={{ color: '#38bdf8', display: 'flex', alignItems: 'center', gap: 2 }}>
                          <ImageIcon size={12} /> Poster
                        </span>
                      )}
                    </div>

                    {/* Governance Findings Summary Tags */}
                    <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {sub.governance_status && (
                        <span style={{
                          fontSize: '0.68rem',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: 4,
                          background: sub.governance_status === 'passed' ? 'rgba(16, 185, 129, 0.15)' : (sub.governance_status === 'warnings' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(239, 68, 68, 0.15)'),
                          color: sub.governance_status === 'passed' ? '#34d399' : (sub.governance_status === 'warnings' ? '#fbbf24' : '#f87171')
                        }}>
                          Gov: {sub.governance_status.toUpperCase()}
                        </span>
                      )}
                      {subHasBlockers && (
                        <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '2px 6px', borderRadius: 4, background: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5' }}>
                          {sub.critical_findings_count} Blocker{sub.critical_findings_count === 1 ? '' : 's'}
                        </span>
                      )}
                      {subHasWarnings && !subHasBlockers && (
                        <span style={{ fontSize: '0.68rem', fontWeight: 600, padding: '2px 6px', borderRadius: 4, background: 'rgba(245, 158, 11, 0.2)', color: '#fde68a' }}>
                          {sub.warning_findings_count} Warning{sub.warning_findings_count === 1 ? '' : 's'}
                        </span>
                      )}
                    </div>

                    <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
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
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              {/* Submission Header */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 10 }}>
                  <div>
                    <h2 className="title-lg">{selectedSub.content_item_title}</h2>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: 4 }}>
                      Brand: <strong>{selectedSub.brand_name}</strong> | Channel: <strong>{selectedSub.channel || 'All Channels'}</strong> | Submitted by: <strong>{selectedSub.submitter_name}</strong> on {new Date(selectedSub.created_at).toLocaleString()}
                    </div>
                  </div>
                  <StatusBadge status={selectedSub.status} />
                </div>

                {/* Immutable Version Lock Pill */}
                <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(0,0,0,0.3)', borderRadius: 8, border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Lock size={13} color="#a5b4fc" />
                    Locked Content Version: <strong>Version {selectedSub.version_num}</strong>
                  </div>
                  <div style={{ fontFamily: 'monospace', fontSize: '0.7rem', color: '#a5b4fc' }}>
                    sha256: {selectedSub.checksum}
                  </div>
                </div>

                {selectedSub.submission_notes && (
                  <div style={{ marginTop: 10, padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 6, fontSize: '0.8rem', color: '#cbd5e1' }}>
                    Creator Note: "{selectedSub.submission_notes}"
                  </div>
                )}
              </div>

              {/* Submitted Creative Asset & Copy Text */}
              <div style={{ display: 'grid', gridTemplateColumns: selectedSub.poster_file_path ? '280px 1fr' : '1fr', gap: 16 }}>
                {selectedSub.poster_file_path && (
                  <div>
                    <div className="flex-between" style={{ marginBottom: 6 }}>
                      <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#93c5fd', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <ImageIcon size={14} /> {selectedSub.is_pdf || selectedSub.poster_file_path.endsWith('.pdf') ? `PDF Deck (${selectedSub.page_count || 1} Pages)` : 'Attached Poster Creative'}
                      </div>
                      {(selectedSub.is_pdf || selectedSub.poster_file_path.endsWith('.pdf')) && (selectedSub.page_count || 1) > 1 && (
                        <span style={{ fontSize: '0.7rem', color: '#a5b4fc', fontWeight: 600 }}>
                          Page {selectedPdfPage} of {selectedSub.page_count}
                        </span>
                      )}
                    </div>

                    {/* PDF Page Selector Chips */}
                    {(selectedSub.is_pdf || selectedSub.poster_file_path.endsWith('.pdf')) && (selectedSub.page_count || 1) > 1 && (
                      <div style={{
                        display: 'flex',
                        gap: 5,
                        overflowX: 'auto',
                        padding: '4px 6px',
                        background: 'rgba(255,255,255,0.03)',
                        borderRadius: 6,
                        marginBottom: 8
                      }}>
                        {Array.from({ length: selectedSub.page_count || 1 }, (_, i) => i + 1).map((pg) => {
                          const isCur = selectedPdfPage === pg;
                          const pgCrit = criticalBlockers.filter(f => f.page_number === pg).length;
                          const pgWarn = warnings.filter(f => f.page_number === pg).length;
                          const dotColor = pgCrit > 0 ? '#fb7185' : (pgWarn > 0 ? '#fbbf24' : '#34d399');
                          return (
                            <button
                              key={pg}
                              type="button"
                              onClick={() => setSelectedPdfPage(pg)}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 4,
                                padding: '2px 6px',
                                borderRadius: 4,
                                border: isCur ? '1px solid #6366f1' : '1px solid rgba(255,255,255,0.1)',
                                background: isCur ? 'rgba(99,102,241,0.25)' : 'rgba(255,255,255,0.04)',
                                color: isCur ? '#fff' : 'var(--text-muted)',
                                fontSize: '0.7rem',
                                fontWeight: isCur ? 700 : 500,
                                cursor: 'pointer'
                              }}
                            >
                              <span style={{ width: 5, height: 5, borderRadius: '50%', background: dotColor }} />
                              p.{pg}
                            </button>
                          );
                        })}
                      </div>
                    )}

                    <div style={{
                      borderRadius: 10,
                      background: 'rgba(0,0,0,0.4)',
                      border: '1px solid var(--border-subtle)',
                      padding: 10,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8
                    }}>
                      <img
                        src={api.getPosterUrl(selectedSub.content_version_id, selectedPdfPage)}
                        alt={selectedSub.poster_alt_text || 'Submitted creative poster'}
                        style={{
                          width: '100%',
                          maxHeight: 220,
                          objectFit: 'contain',
                          borderRadius: 6,
                          background: 'rgba(0,0,0,0.5)'
                        }}
                      />
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        <div>File: <strong>{selectedSub.poster_file_path.split(/[/\\]/).pop()}</strong></div>
                        {selectedSub.poster_alt_text && (
                          <div style={{ marginTop: 4, fontStyle: 'italic', color: '#cbd5e1' }}>
                            Alt: "{selectedSub.poster_alt_text}"
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* Submitted Copy Text */}
                <div>
                  <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>
                    Submitted Copy Text (Immutable)
                  </div>
                  <div style={{
                    padding: 14,
                    borderRadius: 10,
                    background: 'rgba(0,0,0,0.4)',
                    border: '1px solid var(--border-subtle)',
                    fontSize: '0.92rem',
                    lineHeight: 1.6,
                    color: '#fff',
                    whiteSpace: 'pre-wrap',
                    minHeight: selectedSub.poster_file_path ? 220 : 120
                  }}>
                    {selectedSub.body_text}
                  </div>
                </div>
              </div>

              {/* Reviewer Governance Findings Inspector */}
              <div style={{
                borderRadius: 10,
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid var(--border-subtle)',
                padding: 16
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#e2e8f0', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Sparkles size={16} color="#818cf8" /> Governance Evidence & Findings Inspector
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 2 }}>
                      Evaluated {selectedSub.rules_evaluated_count ?? latestGovRun?.rules_evaluated_count ?? 0} active brand rules and {selectedSub.facts_evaluated_count ?? latestGovRun?.facts_evaluated_count ?? 0} verified facts for Version {selectedSub.version_num}.
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <span className={`badge badge-${(selectedSub.governance_status || latestGovRun?.overall_status) === 'passed' ? 'success' : ((selectedSub.governance_status || latestGovRun?.overall_status) === 'warnings' ? 'warning' : 'danger')}`}>
                      {((selectedSub.governance_status || latestGovRun?.overall_status) || 'unknown').toUpperCase()}
                    </span>
                  </div>
                </div>

                {/* Critical Blockers */}
                {criticalBlockers.length > 0 && (
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#f87171', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6, textTransform: 'uppercase' }}>
                      <AlertOctagon size={14} /> Unresolved Critical Blockers ({criticalBlockers.length}) — Hard Gate
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {criticalBlockers.map((f) => (
                        <div
                          key={f.id}
                          style={{
                            padding: 12,
                            borderRadius: 8,
                            background: 'rgba(239, 68, 68, 0.08)',
                            border: '1px solid rgba(239, 68, 68, 0.3)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 6
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                              {(selectedSub.is_pdf || selectedSub.poster_file_path?.endsWith('.pdf')) && (
                                f.page_number ? (
                                  <button
                                    type="button"
                                    onClick={() => setSelectedPdfPage(f.page_number!)}
                                    style={{
                                      fontSize: '0.65rem',
                                      fontWeight: 700,
                                      padding: '1px 6px',
                                      borderRadius: 4,
                                      border: 'none',
                                      background: selectedPdfPage === f.page_number ? '#6366f1' : 'rgba(99, 102, 241, 0.25)',
                                      color: '#fff',
                                      cursor: 'pointer'
                                    }}
                                    title={`Click to preview Page ${f.page_number}`}
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
                              <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#fca5a5' }}>
                                {f.matched_rule_code ? `[${f.matched_rule_code}] ` : ''}{f.title}
                              </div>
                            </div>
                            <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#f87171', background: 'rgba(239, 68, 68, 0.2)', padding: '2px 6px', borderRadius: 4, whiteSpace: 'nowrap' }}>
                              CRITICAL BLOCKER
                            </span>
                          </div>

                          <div style={{ fontSize: '0.8rem', color: '#e2e8f0', lineHeight: 1.4 }}>
                            {f.explanation}
                          </div>

                          {f.text_excerpt && (
                            <div style={{ fontSize: '0.76rem', color: '#cbd5e1', background: 'rgba(0,0,0,0.3)', padding: '6px 10px', borderRadius: 4, fontFamily: 'monospace' }}>
                              Found violation: "{f.text_excerpt}"
                            </div>
                          )}

                          {/* OCR Evidence details if available */}
                          {(f.ocr_confidence !== undefined || f.bounding_box) && (
                            <div style={{ fontSize: '0.72rem', color: '#93c5fd', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                              {f.ocr_confidence !== undefined && (
                                <span>OCR Confidence: <strong>{(f.ocr_confidence * 100).toFixed(1)}%</strong> <em style={{ color: 'var(--text-dim)' }}>(Provisional Heuristic)</em></span>
                              )}
                              {f.bounding_box && (
                                <span>Region: <code>[{f.bounding_box.map((n: number) => Math.round(n)).join(', ')}]</code></span>
                              )}
                            </div>
                          )}

                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.72rem', color: 'var(--text-dim)', borderTop: '1px solid rgba(239, 68, 68, 0.15)', paddingTop: 6, marginTop: 2, flexWrap: 'wrap', gap: 6 }}>
                            <div>Citation: <strong style={{ color: '#cbd5e1' }}>{f.source_citation || 'Brand Guidelines'}</strong></div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <div style={{ color: '#f87171' }}>Action: {f.recommended_action || 'Revise prohibited claim'}</div>
                              <button
                                type="button"
                                onClick={(e) => { e.stopPropagation(); setSelectedFindingForFeedback(f); }}
                                className="btn btn-secondary"
                                style={{ padding: '2px 8px', fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: 4, height: 24 }}
                                title="Record Reviewer Feedback / Flag Ambiguity"
                              >
                                <MessageSquare size={12} /> Feedback
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Warnings / Human Review Requirements */}
                {warnings.length > 0 && (
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#fbbf24', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6, textTransform: 'uppercase' }}>
                      <AlertTriangle size={14} /> Warnings & Human Review Requirements ({warnings.length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {warnings.map((f) => (
                        <div
                          key={f.id}
                          style={{
                            padding: 12,
                            borderRadius: 8,
                            background: 'rgba(245, 158, 11, 0.08)',
                            border: '1px solid rgba(245, 158, 11, 0.3)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 6
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                              {(selectedSub.is_pdf || selectedSub.poster_file_path?.endsWith('.pdf')) && (
                                f.page_number ? (
                                  <button
                                    type="button"
                                    onClick={() => setSelectedPdfPage(f.page_number!)}
                                    style={{
                                      fontSize: '0.65rem',
                                      fontWeight: 700,
                                      padding: '1px 6px',
                                      borderRadius: 4,
                                      border: 'none',
                                      background: selectedPdfPage === f.page_number ? '#6366f1' : 'rgba(99, 102, 241, 0.25)',
                                      color: '#fff',
                                      cursor: 'pointer'
                                    }}
                                    title={`Click to preview Page ${f.page_number}`}
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
                              <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#fde68a' }}>
                                {f.matched_rule_code ? `[${f.matched_rule_code}] ` : ''}{f.title}
                              </div>
                            </div>
                            <span style={{ fontSize: '0.7rem', fontWeight: 600, color: '#fbbf24', background: 'rgba(245, 158, 11, 0.2)', padding: '2px 6px', borderRadius: 4, whiteSpace: 'nowrap' }}>
                              WARNING / OVERRIDEABLE
                            </span>
                          </div>

                          <div style={{ fontSize: '0.8rem', color: '#e2e8f0', lineHeight: 1.4 }}>
                            {f.explanation}
                          </div>

                          {f.text_excerpt && (
                            <div style={{ fontSize: '0.76rem', color: '#cbd5e1', background: 'rgba(0,0,0,0.3)', padding: '6px 10px', borderRadius: 4, fontFamily: 'monospace' }}>
                              Evidence: "{f.text_excerpt}"
                            </div>
                          )}

                          {(f.ocr_confidence !== undefined || f.bounding_box) && (
                            <div style={{ fontSize: '0.72rem', color: '#93c5fd', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                              {f.ocr_confidence !== undefined && (
                                <span>OCR Confidence: <strong>{(f.ocr_confidence * 100).toFixed(1)}%</strong> <em style={{ color: 'var(--text-dim)' }}>(Provisional Heuristic)</em></span>
                              )}
                              {f.bounding_box && (
                                <span>Region: <code>[{f.bounding_box.map((n: number) => Math.round(n)).join(', ')}]</code></span>
                              )}
                            </div>
                          )}

                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.72rem', color: 'var(--text-dim)', borderTop: '1px solid rgba(245, 158, 11, 0.15)', paddingTop: 6, marginTop: 2, flexWrap: 'wrap', gap: 6 }}>
                            <div>Citation: <strong style={{ color: '#cbd5e1' }}>{f.source_citation || 'Brand Guidelines'}</strong></div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <div style={{ color: '#fbbf24' }}>Action: {f.recommended_action || 'Reviewer judgment required'}</div>
                              <button
                                type="button"
                                onClick={(e) => { e.stopPropagation(); setSelectedFindingForFeedback(f); }}
                                className="btn btn-secondary"
                                style={{ padding: '2px 8px', fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: 4, height: 24 }}
                                title="Record Reviewer Feedback / Flag Ambiguity"
                              >
                                <MessageSquare size={12} /> Feedback
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Informational findings */}
                {infoFindings.length > 0 && (
                  <div>
                    <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#93c5fd', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6, textTransform: 'uppercase' }}>
                      <Info size={14} /> Informational Observations ({infoFindings.length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {infoFindings.map((f) => (
                        <div key={f.id} style={{ padding: 10, borderRadius: 6, background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)', fontSize: '0.78rem', color: '#cbd5e1' }}>
                          <div style={{ fontWeight: 600, color: '#e2e8f0' }}>{f.title}</div>
                          <div style={{ marginTop: 2 }}>{f.explanation}</div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: 4 }}>
                            <div>Citation: {f.source_citation}</div>
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); setSelectedFindingForFeedback(f); }}
                              className="btn btn-secondary"
                              style={{ padding: '2px 8px', fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: 4, height: 22 }}
                              title="Record Reviewer Feedback / Flag Ambiguity"
                            >
                              <MessageSquare size={11} /> Feedback
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Clean Pass state */}
                {criticalBlockers.length === 0 && warnings.length === 0 && (
                  <div style={{ padding: '12px 16px', borderRadius: 8, background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)', display: 'flex', alignItems: 'center', gap: 10 }}>
                    <ShieldCheck size={20} color="#34d399" />
                    <div style={{ fontSize: '0.8rem', color: '#a7f3d0' }}>
                      <strong>Clean Compliance Pass:</strong> No critical violations or unresolved warnings found. Content conforms to active guidelines for brand and channel.
                    </div>
                  </div>
                )}
              </div>

              {/* Past Decisions History */}
              {selectedSub.decisions && selectedSub.decisions.length > 0 && (
                <div>
                  <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>
                    Decision Audit History
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {selectedSub.decisions.map((dec) => (
                      <div key={dec.id} style={{ padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: 6, border: '1px solid var(--border-subtle)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 700, fontSize: '0.82rem', color: dec.decision === 'approved' ? '#34d399' : '#fb7185' }}>
                            {dec.decision_label}
                          </span>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
                            {dec.decider_name || 'Approver'} • {new Date(dec.created_at).toLocaleString()}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 2 }}>
                          "{dec.comments}"
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Approval Actions Panel */}
              <div style={{ marginTop: 'auto', paddingTop: 16, borderTop: '1px solid var(--border-subtle)' }}>
                {/* Conflict of interest warning */}
                {isSelfSubmission && (
                  <div style={{ padding: 10, borderRadius: 8, background: 'rgba(244,63,94,0.1)', border: '1px solid rgba(244,63,94,0.3)', color: '#fb7185', fontSize: '0.8rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <ShieldAlert size={16} />
                    <div>
                      <strong>Conflict of Interest Security Rule:</strong> You submitted this content. Creators cannot approve their own drafts. Switch to Marcus Manager (approver@freshsip.demo) to approve.
                    </div>
                  </div>
                )}

                {/* Hard Blocker Notice */}
                {hasCriticalBlockers && (
                  <div style={{ padding: 12, borderRadius: 8, background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.4)', color: '#fca5a5', fontSize: '0.82rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
                    <AlertOctagon size={18} color="#f87171" />
                    <div>
                      <strong>Approval Gate Locked:</strong> Unresolved critical policy violations exist for this content version. By brand policy, critical violations cannot be bypassed under any override. You must Reject or Request Changes.
                    </div>
                  </div>
                )}

                {/* Warning Override Guidance */}
                {hasWarningsOnly && (
                  <div style={{ padding: 10, borderRadius: 8, background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', color: '#fde68a', fontSize: '0.8rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <AlertTriangle size={16} color="#fbbf24" />
                    <div>
                      <strong>Warning Override Policy:</strong> Content contains active warnings. Approving requires recording a substantive justification in the decision comments (minimum 10 characters).
                    </div>
                  </div>
                )}

                <div className="form-group" style={{ marginBottom: 12 }}>
                  <label className="form-label" style={{ fontSize: '0.78rem' }}>
                    Approval Decision Comments {hasWarningsOnly ? '(Substantive Justification Required)' : '(Required)'}
                  </label>
                  <textarea
                    value={decisionNotes}
                    onChange={(e) => setDecisionNotes(e.target.value)}
                    className="textarea"
                    placeholder={
                      hasCriticalBlockers
                        ? "Enter rejection explanation or revision instructions for the creator..."
                        : hasWarningsOnly
                        ? "Enter formal justification explaining why warnings are acceptable (min 10 chars)..."
                        : "Enter formal verification notes or approval rationale..."
                    }
                    style={{ minHeight: 65, fontSize: '0.85rem' }}
                    disabled={!isApprover}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, flexWrap: 'wrap' }}>
                  <button
                    onClick={() => handleDecision('changes_requested')}
                    disabled={!isApprover || deciding || isSelfSubmission}
                    className="btn btn-secondary"
                  >
                    <RotateCcw size={15} /> Request Changes
                  </button>
                  <button
                    onClick={() => handleDecision('rejected')}
                    disabled={!isApprover || deciding || isSelfSubmission}
                    className="btn btn-danger"
                  >
                    <XCircle size={15} /> Reject
                  </button>
                  <button
                    onClick={() => handleDecision('approved')}
                    disabled={!isApprover || deciding || isSelfSubmission || hasCriticalBlockers}
                    className="btn btn-success"
                    title={hasCriticalBlockers ? "Cannot approve: Unresolved critical blockers exist" : ""}
                  >
                    <CheckCircle size={15} /> Approve — Ready to Publish
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <FindingFeedbackModal
        finding={selectedFindingForFeedback}
        isOpen={Boolean(selectedFindingForFeedback)}
        onClose={() => setSelectedFindingForFeedback(null)}
        canReview={role === 'approval_manager' || role === 'knowledge_reviewer' || role === 'org_admin'}
      />
    </div>
  );
};
