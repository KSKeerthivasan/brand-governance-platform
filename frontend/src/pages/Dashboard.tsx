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
  Clock,
  Sparkles,
  BarChart3,
  Filter,
  Layers,
  AlertOctagon,
  Info,
  Calendar,
  CheckCircle2,
  HelpCircle,
  RefreshCw,
  ExternalLink,
  ChevronDown,
  Tag
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { StatusBadge } from '../components/StatusBadge';
import {
  AuditEvent,
  AnalyticsOverview,
  RepeatedMistakesData,
  RepeatedMistakeItem,
  AmbiguityReportData,
  RuleAmbiguityReportItem
} from '../types';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

type DashboardTab = 'overview' | 'recurrence' | 'ambiguity';

export const Dashboard: React.FC = () => {
  const { user, role, organizationName } = useAuth();

  // Active Tab
  const [activeTab, setActiveTab] = useState<DashboardTab>('overview');

  // Filters State
  const [dateRange, setDateRange] = useState<string>('all');
  const [channelFilter, setChannelFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');

  // Top system counter stats
  const [stats, setStats] = useState({
    approvedRules: 0,
    approvedFacts: 0,
    pendingKnowledge: 0,
    activeDrafts: 0,
    pendingApprovals: 0,
  });

  // Analytics Data
  const [overviewData, setOverviewData] = useState<AnalyticsOverview | null>(null);
  const [repeatedData, setRepeatedData] = useState<RepeatedMistakesData | null>(null);
  const [ambiguityData, setAmbiguityData] = useState<AmbiguityReportData | null>(null);

  // Expanded details state for drilldown
  const [expandedRuleId, setExpandedRuleId] = useState<string | null>(null);

  const [recentAudits, setRecentAudits] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  // Helper to build query params
  const buildQueryParams = () => {
    const params: Record<string, string> = {};
    if (channelFilter !== 'all') params.channel = channelFilter;
    if (severityFilter !== 'all') params.severity = severityFilter;

    const now = new Date();
    if (dateRange === '7d') {
      const d = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      params.date_from = d.toISOString();
    } else if (dateRange === '30d') {
      const d = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      params.date_from = d.toISOString();
    } else if (dateRange === '90d') {
      const d = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
      params.date_from = d.toISOString();
    }
    return params;
  };

  const fetchAnalytics = async () => {
    try {
      setAnalyticsLoading(true);
      const params = buildQueryParams();
      const [overview, repeated, ambiguity] = await Promise.all([
        api.getAnalyticsOverview(params),
        api.getRepeatedMistakes(params),
        api.getAmbiguitySignals(params)
      ]);
      setOverviewData(overview);
      setRepeatedData(repeated);
      setAmbiguityData(ambiguity);
    } catch (err) {
      console.error('Failed to load historical analytics:', err);
    } finally {
      setAnalyticsLoading(false);
    }
  };

  const fetchCoreDashboardData = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
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
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    fetchCoreDashboardData(false);
    fetchAnalytics();
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [dateRange, channelFilter, severityFilter]);

  useAutoRefresh(() => {
    fetchCoreDashboardData(true);
    fetchAnalytics();
  }, { intervalMs: 12000 });

  return (
    <div>
      {/* Welcome Banner */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <div style={{ fontSize: '0.85rem', color: '#818cf8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {organizationName || 'Brand Workspace'}
          </div>
          <h1 className="title-xl" style={{ marginTop: 4 }}>
            Historical Governance Analytics & Ambiguity Signals
          </h1>
          <p className="text-sub" style={{ marginTop: 4 }}>
            Evidence-based metrics from recorded review history, recurring mistakes across content drafts, and reviewer ambiguity signals.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <Link to="/content" className="btn btn-primary" id="btn-dashboard-new-draft">
            <FileEdit size={16} /> New Content Draft
          </Link>
          <Link to="/knowledge" className="btn btn-secondary" id="btn-dashboard-knowledge-base">
            <BookOpen size={16} /> Knowledge Base
          </Link>
        </div>
      </div>

      {/* Primary Navigation Tabs */}
      <div style={{
        display: 'flex',
        borderBottom: '1px solid var(--border-subtle)',
        marginBottom: 20,
        gap: 8,
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap'
      }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            id="tab-btn-overview"
            onClick={() => setActiveTab('overview')}
            style={{
              padding: '10px 18px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === 'overview' ? '2px solid #818cf8' : '2px solid transparent',
              color: activeTab === 'overview' ? '#fff' : 'var(--text-dim)',
              fontWeight: 700,
              fontSize: '0.9rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              transition: 'all 0.15s ease'
            }}
          >
            <BarChart3 size={16} color={activeTab === 'overview' ? '#818cf8' : 'currentColor'} />
            Governance Overview
          </button>

          <button
            id="tab-btn-recurrence"
            onClick={() => setActiveTab('recurrence')}
            style={{
              padding: '10px 18px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === 'recurrence' ? '2px solid #818cf8' : '2px solid transparent',
              color: activeTab === 'recurrence' ? '#fff' : 'var(--text-dim)',
              fontWeight: 700,
              fontSize: '0.9rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              transition: 'all 0.15s ease'
            }}
          >
            <Layers size={16} color={activeTab === 'recurrence' ? '#818cf8' : 'currentColor'} />
            Recurring Violations
            {repeatedData && repeatedData.total_repeated_rules_count > 0 && (
              <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: 10, background: 'rgba(99,102,241,0.2)', color: '#a5b4fc', fontWeight: 700 }}>
                {repeatedData.total_repeated_rules_count}
              </span>
            )}
          </button>

          <button
            id="tab-btn-ambiguity"
            onClick={() => setActiveTab('ambiguity')}
            style={{
              padding: '10px 18px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === 'ambiguity' ? '2px solid #818cf8' : '2px solid transparent',
              color: activeTab === 'ambiguity' ? '#fff' : 'var(--text-dim)',
              fontWeight: 700,
              fontSize: '0.9rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              transition: 'all 0.15s ease'
            }}
          >
            <HelpCircle size={16} color={activeTab === 'ambiguity' ? '#a855f7' : 'currentColor'} />
            Guideline Ambiguity Signals
            {ambiguityData && ambiguityData.flagged_rules_count > 0 && (
              <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: 10, background: 'rgba(168,85,247,0.2)', color: '#d8b4fe', fontWeight: 700 }}>
                {ambiguityData.flagged_rules_count} Flagged
              </span>
            )}
          </button>
        </div>

        {/* Global Filter Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Calendar size={14} color="var(--text-dim)" />
            <select
              id="filter-date-range"
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              style={{
                background: '#1e293b',
                border: '1px solid var(--border-subtle)',
                color: '#cbd5e1',
                padding: '4px 10px',
                borderRadius: 6,
                fontSize: '0.78rem'
              }}
            >
              <option value="all">All Time</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="90d">Last 90 Days</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Filter size={14} color="var(--text-dim)" />
            <select
              id="filter-channel"
              value={channelFilter}
              onChange={(e) => setChannelFilter(e.target.value)}
              style={{
                background: '#1e293b',
                border: '1px solid var(--border-subtle)',
                color: '#cbd5e1',
                padding: '4px 10px',
                borderRadius: 6,
                fontSize: '0.78rem'
              }}
            >
              <option value="all">All Channels</option>
              <option value="instagram">Instagram</option>
              <option value="print">Print Poster</option>
              <option value="web">Web / Blog</option>
              <option value="email">Email</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <select
              id="filter-severity"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              style={{
                background: '#1e293b',
                border: '1px solid var(--border-subtle)',
                color: '#cbd5e1',
                padding: '4px 10px',
                borderRadius: 6,
                fontSize: '0.78rem'
              }}
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical Only</option>
              <option value="warning">Warning Only</option>
              <option value="info">Info Only</option>
            </select>
          </div>

          <button
            onClick={() => fetchAnalytics()}
            title="Refresh analytics data"
            style={{
              background: 'transparent',
              border: '1px solid var(--border-subtle)',
              borderRadius: 6,
              padding: '4px 8px',
              color: 'var(--text-dim)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center'
            }}
          >
            <RefreshCw size={13} className={analyticsLoading ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {/* ============================================================== */}
      {/* TAB 1: GOVERNANCE OVERVIEW                                     */}
      {/* ============================================================== */}
      {activeTab === 'overview' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Top High-level KPIs */}
          <div className="grid-4">
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="text-sub" style={{ fontWeight: 600 }}>Total Governance Runs</span>
                <div style={{ width: 34, height: 34, borderRadius: 8, background: 'rgba(99,102,241,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#818cf8' }}>
                  <TrendingUp size={18} />
                </div>
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', marginTop: 12 }}>
                {overviewData ? overviewData.total_runs : (loading ? '...' : 0)}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
                Selected period execution count
              </div>
            </div>

            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="text-sub" style={{ fontWeight: 600 }}>Runs With Actionable Issues</span>
                <div style={{ width: 34, height: 34, borderRadius: 8, background: 'rgba(239,68,68,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#f87171' }}>
                  <AlertOctagon size={18} />
                </div>
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#f87171', marginTop: 12 }}>
                {overviewData ? overviewData.runs_with_findings_count : (loading ? '...' : 0)}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
                {overviewData && overviewData.total_runs > 0 ? (
                  <span>
                    <strong style={{ color: '#fca5a5' }}>{overviewData.runs_with_findings_pct}%</strong> of total runs (denominator: {overviewData.total_runs})
                  </span>
                ) : 'No runs recorded'}
              </div>
            </div>

            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="text-sub" style={{ fontWeight: 600 }}>Clean Governance Passes</span>
                <div style={{ width: 34, height: 34, borderRadius: 8, background: 'rgba(16,185,129,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#34d399' }}>
                  <CheckCircle size={18} />
                </div>
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#34d399', marginTop: 12 }}>
                {overviewData ? overviewData.clean_runs_count : (loading ? '...' : 0)}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
                {overviewData && overviewData.total_runs > 0 ? (
                  <span>
                    <strong style={{ color: '#6ee7b7' }}>{overviewData.clean_runs_pct}%</strong> clean rate (denominator: {overviewData.total_runs})
                  </span>
                ) : 'No runs recorded'}
              </div>
            </div>

            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="text-sub" style={{ fontWeight: 600 }}>Total Findings Logged</span>
                <div style={{ width: 34, height: 34, borderRadius: 8, background: 'rgba(245,158,11,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fbbf24' }}>
                  <AlertTriangle size={18} />
                </div>
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', marginTop: 12 }}>
                {overviewData ? overviewData.total_findings : (loading ? '...' : 0)}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
                {overviewData ? (
                  <span>
                    <strong style={{ color: '#fca5a5' }}>{overviewData.actionable_findings_count}</strong> actionable •{' '}
                    <strong style={{ color: '#86efac' }}>{overviewData.successful_checks_count}</strong> passed
                  </span>
                ) : 'Across all evaluated rules & facts'}
              </div>
            </div>
          </div>

          {/* Breakdown: Severity & Finding Categories */}
          <div className="grid-2">
            {/* Severity Distribution Card */}
            <div className="card">
              <div className="flex-between" style={{ marginBottom: 14 }}>
                <h2 className="title-md" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <ShieldCheck size={18} color="#818cf8" /> Findings Classification & Severity
                </h2>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                  Total: {overviewData?.total_findings || 0} checks
                </span>
              </div>

              {!overviewData || overviewData.total_findings === 0 ? (
                <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-dim)' }}>
                  No governance findings recorded for the selected filter window.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {/* Actionable vs Passed Summary Pill */}
                  <div style={{ display: 'flex', gap: 8, padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 6, fontSize: '0.76rem', justifyContent: 'space-between' }}>
                    <span>Actionable Issues: <strong style={{ color: '#f87171' }}>{overviewData.actionable_findings_count}</strong> ({overviewData.actionable_findings_pct}%)</span>
                    <span>Passed Checks: <strong style={{ color: '#34d399' }}>{overviewData.successful_checks_count}</strong> ({overviewData.successful_checks_pct}%)</span>
                    <span>Unresolved: <strong style={{ color: '#38bdf8' }}>{overviewData.unresolved_review_count}</strong> ({overviewData.unresolved_review_pct}%)</span>
                  </div>

                  {/* Critical */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, color: '#fca5a5', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <AlertOctagon size={14} color="#f87171" /> Critical Hard Blockers
                      </span>
                      <span>
                        <strong style={{ color: '#fff' }}>{overviewData.actionable_findings_by_severity?.['critical'] || overviewData.findings_by_severity['critical'] || 0}</strong> ({overviewData.actionable_findings_by_severity_pct?.['critical'] || overviewData.findings_by_severity_pct['critical'] || 0}% of actionable)
                      </span>
                    </div>
                    <div style={{ height: 8, background: 'rgba(255,255,255,0.06)', borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${overviewData.actionable_findings_by_severity_pct?.['critical'] || overviewData.findings_by_severity_pct['critical'] || 0}%`, background: '#ef4444', borderRadius: 4 }} />
                    </div>
                  </div>

                  {/* Warning */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, color: '#fde68a', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <AlertTriangle size={14} color="#fbbf24" /> Warnings (Overrideable)
                      </span>
                      <span>
                        <strong style={{ color: '#fff' }}>{overviewData.actionable_findings_by_severity?.['warning'] || overviewData.findings_by_severity['warning'] || 0}</strong> ({overviewData.actionable_findings_by_severity_pct?.['warning'] || overviewData.findings_by_severity_pct['warning'] || 0}% of actionable)
                      </span>
                    </div>
                    <div style={{ height: 8, background: 'rgba(255,255,255,0.06)', borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${overviewData.actionable_findings_by_severity_pct?.['warning'] || overviewData.findings_by_severity_pct['warning'] || 0}%`, background: '#f59e0b', borderRadius: 4 }} />
                    </div>
                  </div>

                  {/* Info */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, color: '#93c5fd', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Info size={14} color="#3b82f6" /> Actionable Informational Reviews
                      </span>
                      <span>
                        <strong style={{ color: '#fff' }}>{overviewData.actionable_findings_by_severity?.['info'] || 0}</strong> ({overviewData.actionable_findings_by_severity_pct?.['info'] || 0}% of actionable)
                      </span>
                    </div>
                    <div style={{ height: 8, background: 'rgba(255,255,255,0.06)', borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${overviewData.actionable_findings_by_severity_pct?.['info'] || 0}%`, background: '#3b82f6', borderRadius: 4 }} />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Findings by Category */}
            <div className="card">
              <div className="flex-between" style={{ marginBottom: 14 }}>
                <h2 className="title-md" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Tag size={18} color="#818cf8" /> Findings by Governance Category
                </h2>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                  Targeted policy domains
                </span>
              </div>

              {!overviewData || Object.keys(overviewData.findings_by_category).length === 0 ? (
                <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-dim)' }}>
                  No categorized findings recorded in this timeframe.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {Object.entries(overviewData.findings_by_category).map(([cat, count]) => {
                    const pct = overviewData.total_findings > 0 ? Math.round((count / overviewData.total_findings) * 100) : 0;
                    return (
                      <div key={cat} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: 6 }}>
                        <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#e2e8f0', textTransform: 'capitalize' }}>
                          {cat.replace(/_/g, ' ')}
                        </span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: '0.8rem', color: '#a5b4fc', fontWeight: 700 }}>
                            {count}
                          </span>
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                            ({pct}%)
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Chronological Activity Timeline */}
          {overviewData && overviewData.runs_over_time.length > 0 && (
            <div className="card">
              <h2 className="title-md" style={{ marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Clock size={18} color="#818cf8" /> Governance Activity Over Time
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(overviewData.runs_over_time.length, 12)}, 1fr)`, gap: 10 }}>
                {overviewData.runs_over_time.slice(-12).map((day) => (
                  <div
                    key={day.date}
                    style={{
                      padding: 10,
                      background: 'rgba(255,255,255,0.02)',
                      borderRadius: 8,
                      border: '1px solid var(--border-subtle)',
                      textAlign: 'center'
                    }}
                  >
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 600 }}>{day.date.substring(5)}</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#fff', marginTop: 4 }}>{day.runs_count}</div>
                    <div style={{ fontSize: '0.68rem', color: day.findings_count > 0 ? '#f87171' : '#34d399', marginTop: 2 }}>
                      {day.findings_count} finding{day.findings_count === 1 ? '' : 's'}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Quick Workflows & Live Audit Trail */}
          <div className="grid-2">
            <div className="card">
              <h2 className="title-md" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                <TrendingUp size={18} color="#818cf8" /> Governance Operations
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
                      Authorized approval manager review with inline finding feedback.
                    </div>
                  </div>
                  <ArrowRight size={18} color="#818cf8" />
                </Link>
              </div>
            </div>

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
                  {recentAudits.slice(0, 5).map((event) => (
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
      )}

      {/* ============================================================== */}
      {/* TAB 2: RECURRING VIOLATIONS (REPEATED MISTAKES)                */}
      {/* ============================================================== */}
      {activeTab === 'recurrence' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Explanation Banner */}
          <div style={{
            padding: 16,
            borderRadius: 10,
            background: 'rgba(99, 102, 241, 0.08)',
            border: '1px solid rgba(99, 102, 241, 0.25)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: 12
          }}>
            <Layers size={20} color="#818cf8" style={{ marginTop: 2, flexShrink: 0 }} />
            <div>
              <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#e0e7ff' }}>
                Repeated Governance Violations Across Content Items
              </div>
              <div style={{ fontSize: '0.8rem', color: '#c7d2fe', marginTop: 4, lineHeight: 1.4 }}>
                Ranked by <strong>distinct content items affected</strong> rather than raw finding frequency. Multiple violations within a single document are not conflated with cross-draft recurrence. Reappearance across revision cycles is tracked separately.
              </div>
            </div>
          </div>

          {!repeatedData || repeatedData.items.length === 0 ? (
            <div className="card" style={{ padding: 48, textAlign: 'center' }}>
              <CheckCircle2 size={36} color="#34d399" style={{ margin: '0 auto 12px auto' }} />
              <div style={{ fontWeight: 700, fontSize: '1.1rem', color: '#fff' }}>No Repeated Violations Detected</div>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-dim)', maxWidth: 460, margin: '6px auto 0 auto' }}>
                No brand rules triggered across multiple content items for the current filter criteria ({dateRange}, {channelFilter}, {severityFilter}).
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {repeatedData.items.map((item, idx) => {
                const isExpanded = expandedRuleId === item.rule_id;
                const trendColor = item.recurrence_trend === 'increasing' ? '#f87171' : (item.recurrence_trend === 'decreasing' ? '#34d399' : (item.recurrence_trend === 'stable' ? '#fbbf24' : 'var(--text-dim)'));

                return (
                  <div
                    key={item.rule_id}
                    className="card"
                    style={{
                      padding: 18,
                      border: isExpanded ? '1px solid rgba(99,102,241,0.4)' : '1px solid var(--border-subtle)',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#818cf8', background: 'rgba(99,102,241,0.15)', padding: '2px 8px', borderRadius: 4 }}>
                            #{idx + 1}
                          </span>
                          {item.rule_code && (
                            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#a5b4fc', background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: 4 }}>
                              {item.rule_code}
                            </span>
                          )}
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>
                            {item.rule_type} • {item.category}
                          </span>
                        </div>

                        <div style={{ fontWeight: 700, fontSize: '1rem', color: '#fff', marginTop: 6 }}>
                          {item.rule_title}
                        </div>
                      </div>

                      {/* Recurrence Metrics Badge Group */}
                      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                        <div style={{ textAlign: 'center', padding: '6px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
                          <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff' }}>
                            {item.distinct_content_items_count}
                          </div>
                          <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>
                            Distinct Items
                          </div>
                        </div>

                        <div style={{ textAlign: 'center', padding: '6px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
                          <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#cbd5e1' }}>
                            {item.total_findings}
                          </div>
                          <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>
                            Total Findings
                          </div>
                        </div>

                        {/* Trend indicator */}
                        <div style={{
                          padding: '6px 12px',
                          borderRadius: 8,
                          background: `${trendColor}15`,
                          border: `1px solid ${trendColor}40`,
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          justifyContent: 'center',
                          minWidth: 100
                        }}>
                          <span style={{ fontSize: '0.72rem', fontWeight: 800, color: trendColor, textTransform: 'uppercase' }}>
                            {item.recurrence_trend.replace(/_/g, ' ')}
                          </span>
                          <span style={{ fontSize: '0.65rem', color: 'var(--text-dim)' }}>
                            Trend Signal
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Breakdown & Context */}
                    <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                        <span>
                          Severity: <strong style={{ color: item.severity_distribution['critical'] ? '#fca5a5' : '#fde68a' }}>
                            {item.severity_distribution['critical'] || 0} critical, {item.severity_distribution['warning'] || 0} warning
                          </strong>
                        </span>
                        <span>•</span>
                        <span>
                          Revisions: <strong style={{ color: item.recurrent_version_issues_count > 0 ? '#fca5a5' : '#cbd5e1' }}>
                            {item.recurrent_version_issues_count} item(s) recurred after revision
                          </strong>
                        </span>
                        {Object.keys(item.channels_distribution).length > 0 && (
                          <>
                            <span>•</span>
                            <span>
                              Channels: {Object.entries(item.channels_distribution).map(([ch, cnt]) => `${ch} (${cnt})`).join(', ')}
                            </span>
                          </>
                        )}
                      </div>

                      <button
                        onClick={() => setExpandedRuleId(isExpanded ? null : item.rule_id)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#818cf8',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 4
                        }}
                      >
                        {isExpanded ? 'Hide Details' : 'Inspect Rule & Evidence'}
                        <ChevronDown size={14} style={{ transform: isExpanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s ease' }} />
                      </button>
                    </div>

                    {/* Expanded Detail Panel */}
                    {isExpanded && (
                      <div style={{ marginTop: 12, padding: 14, background: 'rgba(0,0,0,0.25)', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
                        <div style={{ fontSize: '0.75rem', color: '#a5b4fc', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                          Trend Rationale & Persistence Details
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#cbd5e1', marginTop: 4 }}>
                          {item.trend_details || 'Trend evaluated by partitioning historical occurrences into chronologically ordered time windows.'}
                        </div>
                        <div style={{ marginTop: 10, display: 'flex', gap: 10 }}>
                          <Link to="/knowledge" className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                            <BookOpen size={13} /> View Rule in Knowledge Base
                          </Link>
                          <Link to="/content" className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                            <FileEdit size={13} /> Test Copy in Studio
                          </Link>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ============================================================== */}
      {/* TAB 3: GUIDELINE AMBIGUITY SIGNALS                             */}
      {/* ============================================================== */}
      {activeTab === 'ambiguity' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Ambiguity Methodology Explanation Banner */}
          <div style={{
            padding: 16,
            borderRadius: 10,
            background: 'rgba(168, 85, 247, 0.08)',
            border: '1px solid rgba(168, 85, 247, 0.25)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: 12
          }}>
            <HelpCircle size={20} color="#a855f7" style={{ marginTop: 2, flexShrink: 0 }} />
            <div>
              <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#f3e8ff' }}>
                Evidence-Based Guideline Ambiguity Report (Knowledge Managers)
              </div>
              <div style={{ fontSize: '0.8rem', color: '#e9d5ff', marginTop: 4, lineHeight: 1.4 }}>
                <strong>Important Principle:</strong> High violation count alone does not prove a rule is ambiguous. Rules are flagged based on <em>recorded reviewer dispositions</em> (e.g., guideline unclear, conflicting guidelines, false positive rate) and frequent justified warning overrides. Results represent potential signals for human knowledge managers to review—<strong>rules are never automatically modified or deactivated</strong>.
              </div>
            </div>
          </div>

          {!ambiguityData || ambiguityData.rules.length === 0 ? (
            <div className="card" style={{ padding: 48, textAlign: 'center' }}>
              <ShieldCheck size={36} color="#34d399" style={{ margin: '0 auto 12px auto' }} />
              <div style={{ fontWeight: 700, fontSize: '1.1rem', color: '#fff' }}>No Ambiguity Signals Detected</div>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-dim)', maxWidth: 480, margin: '6px auto 0 auto' }}>
                No active guidelines have accumulated reviewer feedback indicating ambiguity, conflicts, elevated false positives, or repeated warning overrides.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {ambiguityData.rules.map((rule) => {
                const isExpanded = expandedRuleId === rule.rule_id;
                const levelColor = rule.ambiguity_level === 'high' ? '#f87171' : (rule.ambiguity_level === 'medium' ? '#fbbf24' : '#38bdf8');

                return (
                  <div
                    key={rule.rule_id}
                    className="card"
                    style={{
                      padding: 20,
                      border: isExpanded ? '1px solid rgba(168,85,247,0.4)' : '1px solid var(--border-subtle)'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                          <span style={{
                            fontSize: '0.72rem',
                            fontWeight: 800,
                            padding: '3px 8px',
                            borderRadius: 6,
                            background: `${levelColor}20`,
                            color: levelColor,
                            border: `1px solid ${levelColor}40`,
                            textTransform: 'uppercase'
                          }}>
                            {rule.ambiguity_level} Ambiguity Signal
                          </span>
                          {rule.evidence_base_size === 'small' && (
                            <span style={{
                              fontSize: '0.7rem',
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: 4,
                              background: 'rgba(234, 179, 8, 0.15)',
                              color: '#fde047',
                              border: '1px solid rgba(234, 179, 8, 0.3)'
                            }}>
                              Small Evidence Base (&lt; 3 Dispositions)
                            </span>
                          )}
                          {rule.rule_code && (
                            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#a5b4fc', background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: 4 }}>
                              {rule.rule_code}
                            </span>
                          )}
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                            Score: <strong>{rule.ambiguity_score}</strong>
                          </span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                            • Reviewed Findings: <strong style={{ color: '#cbd5e1' }}>{rule.total_dispositions_count}</strong>
                            {rule.total_events_count && rule.total_events_count > rule.total_dispositions_count ? (
                              <span style={{ color: '#a5b4fc', marginLeft: 4 }}>({rule.total_events_count} feedback events)</span>
                            ) : null}
                          </span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                            • Items: <strong style={{ color: '#cbd5e1' }}>{rule.distinct_content_items_count}</strong>
                          </span>
                        </div>

                        <div style={{ fontWeight: 700, fontSize: '1.05rem', color: '#fff', marginTop: 8 }}>
                          {rule.rule_title}
                        </div>

                        {rule.source_citation && (
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
                            Citation: <strong style={{ color: '#cbd5e1' }}>{rule.source_citation}</strong>
                          </div>
                        )}
                      </div>

                      {/* Dispositions breakdown summary */}
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        {Object.entries(rule.dispositions_breakdown).map(([disp, count]) => (
                          <div
                            key={disp}
                            style={{
                              padding: '4px 10px',
                              borderRadius: 6,
                              background: 'rgba(255,255,255,0.03)',
                              border: '1px solid var(--border-subtle)',
                              fontSize: '0.72rem'
                            }}
                          >
                            <span style={{ color: 'var(--text-dim)', textTransform: 'capitalize' }}>{disp.replace(/_/g, ' ')}:</span>{' '}
                            <strong style={{ color: '#fff' }}>{count}</strong>
                          </div>
                        ))}
                        {rule.verified_rule_overrides_count > 0 && (
                          <div style={{ padding: '4px 10px', borderRadius: 6, background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)', fontSize: '0.72rem' }}>
                            <span style={{ color: '#fbbf24' }}>Verified Overrides:</span> <strong style={{ color: '#fff' }}>{rule.verified_rule_overrides_count}</strong>
                          </div>
                        )}
                        {rule.content_level_overrides_count > 0 && (
                          <div style={{ padding: '4px 10px', borderRadius: 6, background: 'rgba(148,163,184,0.08)', border: '1px solid rgba(148,163,184,0.2)', fontSize: '0.72rem' }} title="Multi-rule warning approval without specific citation; excluded from ambiguity score">
                            <span style={{ color: '#94a3b8' }}>Multi-Rule Overrides (Excluded):</span> <strong style={{ color: '#cbd5e1' }}>{rule.content_level_overrides_count}</strong>
                          </div>
                        )}
                      </div>
                    </div>

                    {rule.override_attribution_notes && (
                      <div style={{ marginTop: 10, padding: '8px 12px', background: 'rgba(148,163,184,0.06)', borderRadius: 6, border: '1px solid rgba(148,163,184,0.15)', fontSize: '0.75rem', color: '#94a3b8' }}>
                        ℹ️ {rule.override_attribution_notes}
                      </div>
                    )}

                    {/* Signal Evidence Items */}
                    <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {rule.signals.map((sig, sIdx) => (
                        <div
                          key={sIdx}
                          style={{
                            padding: '10px 14px',
                            borderRadius: 8,
                            background: 'rgba(255,255,255,0.02)',
                            border: '1px solid var(--border-subtle)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 4
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 700, fontSize: '0.82rem', color: '#e2e8f0' }}>
                              {sig.title}
                            </span>
                            <span style={{ fontSize: '0.72rem', color: '#a855f7', fontWeight: 600 }}>
                              {sig.count} / {sig.denominator} distinct findings ({sig.percentage}%)
                              {sig.event_count && sig.event_count > sig.count ? (
                                <span style={{ color: '#cbd5e1', marginLeft: 6 }}>({sig.event_count} feedback events)</span>
                              ) : null}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                            {sig.description}
                          </div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', display: 'flex', gap: 12 }}>
                            <span>Source: <strong style={{ color: '#cbd5e1' }}>{sig.evidence_source === 'approval_decision' ? 'Approval Justification' : 'Reviewer Feedback'}</strong></span>
                            <span>Distinct Items: <strong style={{ color: '#cbd5e1' }}>{sig.distinct_content_items_count || 0}</strong></span>
                            <span>Distinct Findings: <strong style={{ color: '#cbd5e1' }}>{sig.distinct_findings_count || 0}</strong></span>
                          </div>

                          {/* Reviewer Quotes/Feedback */}
                          {sig.sample_feedback && sig.sample_feedback.length > 0 && (
                            <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 4 }}>
                              <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 700 }}>
                                Supporting Reviewer Feedback Samples:
                              </div>
                              {sig.sample_feedback.map((quote, qIdx) => (
                                <div key={qIdx} style={{ fontSize: '0.75rem', color: '#d8b4fe', fontStyle: 'italic', background: 'rgba(168,85,247,0.06)', padding: '4px 10px', borderRadius: 4 }}>
                                  "{quote}"
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>

                    {/* Recommended Action & KB Navigation */}
                    <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
                      <div style={{ fontSize: '0.78rem', color: '#a5b4fc', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Sparkles size={14} color="#818cf8" />
                        <span><strong>Recommended Action:</strong> {rule.recommended_action}</span>
                      </div>

                      <Link
                        to="/knowledge"
                        className="btn btn-secondary"
                        style={{ padding: '4px 12px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 6 }}
                      >
                        <BookOpen size={13} /> Review in Knowledge Base
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
