import React, { useEffect, useState } from 'react';
import { History, Filter, Search, Shield, User, Calendar } from 'lucide-react';
import { api } from '../services/api';
import { AuditEvent } from '../types';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

export const AuditHistory: React.FC = () => {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [filterType, setFilterType] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);

  const loadAuditEvents = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const evs = await api.getAuditEvents(100, filterType === 'all' ? undefined : filterType);
      setEvents(evs);
    } catch (err) {
      console.error('Failed to load audit events:', err);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    loadAuditEvents(false);
  }, [filterType]);

  useAutoRefresh(() => loadAuditEvents(true), { intervalMs: 6000 });

  const filteredEvents = events.filter(e => {
    if (!searchTerm) return true;
    return (
      e.summary.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.event_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (e.user_name && e.user_name.toLowerCase().includes(searchTerm.toLowerCase()))
    );
  });

  return (
    <div>
      <div className="flex-between" style={{ marginBottom: 24 }}>
        <div>
          <h1 className="title-xl">Audit History & State Transitions</h1>
          <p className="text-sub">
            Immutable log of all knowledge reviews, content revisions, governance checks, and approval decisions.
          </p>
        </div>

        {/* Filter Controls */}
        <div style={{ display: 'flex', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--bg-input)', padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
            <Search size={14} color="var(--text-dim)" />
            <input
              type="text"
              placeholder="Search audit trail..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '0.8rem', outline: 'none', width: 160 }}
            />
          </div>

          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="select"
            style={{ width: 'auto', padding: '6px 12px', fontSize: '0.8rem' }}
          >
            <option value="all">All Event Types</option>
            <option value="KNOWLEDGE_UPLOADED">Knowledge Uploaded</option>
            <option value="RULE_APPROVED">Rule Approved</option>
            <option value="FACT_APPROVED">Fact Approved</option>
            <option value="CONTENT_CREATED">Content Created</option>
            <option value="CONTENT_REVISED">Content Revised</option>
            <option value="GOVERNANCE_CHECK_RUN">Governance Run</option>
            <option value="APPROVAL_SUBMITTED">Approval Submitted</option>
            <option value="APPROVAL_APPROVED">Approval Approved</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="card" style={{ textAlign: 'center', padding: 60, color: 'var(--text-dim)' }}>
          Loading audit events...
        </div>
      ) : filteredEvents.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 60, color: 'var(--text-dim)' }}>
          No audit records found matching criteria.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filteredEvents.map((e) => (
            <div
              key={e.id}
              className="card"
              style={{
                padding: '14px 18px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{
                  width: 38,
                  height: 38,
                  borderRadius: 8,
                  background: 'rgba(99, 102, 241, 0.12)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#818cf8',
                  flexShrink: 0
                }}>
                  <History size={18} />
                </div>

                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px', borderRadius: 4, background: 'rgba(255,255,255,0.06)', color: '#cbd5e1', letterSpacing: '0.04em' }}>
                      {e.event_type}
                    </span>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                      Entity: <strong style={{ color: 'var(--text-muted)' }}>{e.entity_type}</strong>
                    </span>
                  </div>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#fff', marginTop: 4 }}>
                    {e.summary}
                  </div>
                  <div style={{ display: 'flex', gap: 16, fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
                    <span>Actor: <strong style={{ color: '#a5b4fc' }}>{e.user_name || 'System'}</strong></span>
                    <span>Entity ID: <code style={{ fontSize: '0.7rem' }}>{e.entity_id.slice(0, 8)}...</code></span>
                  </div>
                </div>
              </div>

              <div style={{ textAlign: 'right', flexShrink: 0, fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                <div>{new Date(e.created_at).toLocaleDateString()}</div>
                <div style={{ color: 'var(--text-muted)', fontWeight: 600, marginTop: 2 }}>
                  {new Date(e.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
