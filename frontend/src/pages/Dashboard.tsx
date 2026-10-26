import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldCheck,
  BookOpen,
  FileEdit,
  CheckCircle,
  AlertTriangle,
  History,
  ArrowRight,
  TrendingUp,
  Clock
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { StatusBadge } from '../components/StatusBadge';
import { AuditEvent } from '../types';

export const Dashboard: React.FC = () => {
  const { user, organizationName } = useAuth();
  const [stats, setStats] = useState({
    approvedRules: 0,
    approvedFacts: 0,
    pendingKnowledge: 0,
    activeDrafts: 0,
    pendingApprovals: 0,
  });
  const [recentAudits, setRecentAudits] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        const [rules, facts, sources, drafts, queue, audits] = await Promise.all([
          api.getRules(),
          api.getFacts(),
          api.getKnowledgeSources(),
          api.getContentItems(),
          api.getApprovalQueue(),
          api.getAuditEvents(8)
        ]);

        const appRules = rules.filter(r => r.status === 'approved').length;
        const appFacts = facts.filter(f => f.status === 'approved').length;
        const pendRules = rules.filter(r => r.status === 'pending_review').length;
        const pendFacts = facts.filter(f => f.status === 'pending_review').length;
        const pendQueue = queue.filter(q => q.status === 'pending').length;

        setStats({
          approvedRules: appRules,
          approvedFacts: appFacts,
          pendingKnowledge: pendRules + pendFacts,
          activeDrafts: drafts.length,
          pendingApprovals: pendQueue,
        });
        setRecentAudits(audits);
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, []);

  return (
    <div>
      {/* Welcome Banner */}
      <div style={{ marginBottom: 28, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <div style={{ fontSize: '0.85rem', color: '#818cf8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {organizationName || 'Freshsip Workspace'}
          </div>
          <h1 className="title-xl" style={{ marginTop: 4 }}>
            Brand Governance Overview
          </h1>
          <p className="text-sub" style={{ marginTop: 4 }}>
            Deterministic rule validation, knowledge truth enforcement, and publication approvals.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <Link to="/content" className="btn btn-primary">
            <FileEdit size={16} /> New Content Draft
          </Link>
          <Link to="/knowledge" className="btn btn-secondary">
            <BookOpen size={16} /> Knowledge Base
          </Link>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid-4" style={{ marginBottom: 28 }}>
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="text-sub" style={{ fontWeight: 600 }}>Approved Rules</span>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: 'rgba(99,102,241,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#818cf8' }}>
              <ShieldCheck size={18} />
            </div>
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', marginTop: 12 }}>
            {loading ? '...' : stats.approvedRules}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
            Brand tone, prohibited wording & policy rules
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="text-sub" style={{ fontWeight: 600 }}>Approved Facts</span>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: 'rgba(16,185,129,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#34d399' }}>
              <CheckCircle size={18} />
            </div>
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', marginTop: 12 }}>
            {loading ? '...' : stats.approvedFacts}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
            Verified product specifications & claims
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="text-sub" style={{ fontWeight: 600 }}>Pending Review</span>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: 'rgba(245,158,11,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fbbf24' }}>
              <AlertTriangle size={18} />
            </div>
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fbbf24', marginTop: 12 }}>
            {loading ? '...' : stats.pendingKnowledge}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
            Candidate records requiring human review
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="text-sub" style={{ fontWeight: 600 }}>Approval Queue</span>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: 'rgba(6,182,212,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#38bdf8' }}>
              <Clock size={18} />
            </div>
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', marginTop: 12 }}>
            {loading ? '...' : stats.pendingApprovals}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
            Submitted content versions pending manager signoff
          </div>
        </div>
      </div>

      {/* Main Grid: Workflows & Live Audit History */}
      <div className="grid-2">
        {/* Quick Workflows */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <h2 className="title-md" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <TrendingUp size={18} color="#818cf8" /> Core Governance Workflows
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <Link to="/content" className="card card-hoverable" style={{ padding: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between', textDecoration: 'none' }}>
                <div>
                  <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.9rem' }}>1. Draft & Governance Checker</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    Compose marketing copy and inspect deterministic rule & fact findings.
                  </div>
                </div>
                <ArrowRight size={18} color="#818cf8" />
              </Link>

              <Link to="/knowledge" className="card card-hoverable" style={{ padding: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between', textDecoration: 'none' }}>
                <div>
                  <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.9rem' }}>2. Knowledge Review Queue</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    Upload brand guidelines and inspect candidate rules before approval.
                  </div>
                </div>
                <ArrowRight size={18} color="#818cf8" />
              </Link>

              <Link to="/approvals" className="card card-hoverable" style={{ padding: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between', textDecoration: 'none' }}>
                <div>
                  <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.9rem' }}>3. Publication Approval Queue</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    Authorized approval manager review for immutable submitted versions.
                  </div>
                </div>
                <ArrowRight size={18} color="#818cf8" />
              </Link>

              <Link to="/image-governance" className="card card-hoverable" style={{ padding: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between', textDecoration: 'none' }}>
                <div>
                  <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.9rem' }}>4. Static-Image Governance (Round 3)</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    Validate aspect ratios, color modes, logo clearspaces, and alt text.
                  </div>
                </div>
                <ArrowRight size={18} color="#818cf8" />
              </Link>
            </div>
          </div>
        </div>

        {/* Live Audit Log Feed */}
        <div className="card">
          <div className="flex-between" style={{ marginBottom: 16 }}>
            <h2 className="title-md" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <History size={18} color="#818cf8" /> Live Audit Trail
            </h2>
            <Link to="/audit" style={{ fontSize: '0.8rem', color: '#818cf8', textDecoration: 'none', fontWeight: 600 }}>
              View All →
            </Link>
          </div>

          {loading ? (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-dim)' }}>Loading audit events...</div>
          ) : recentAudits.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-dim)' }}>No audit events recorded yet.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {recentAudits.map((event) => (
                <div
                  key={event.id}
                  style={{
                    padding: '10px 12px',
                    borderRadius: 8,
                    background: 'rgba(255,255,255,0.02)',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 3
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#a5b4fc', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      {event.event_type.replace(/_/g, ' ')}
                    </span>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
                      {new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-main)', fontWeight: 500 }}>
                    {event.summary}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                    Actor: <span style={{ color: 'var(--text-muted)' }}>{event.user_name || 'System'}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
