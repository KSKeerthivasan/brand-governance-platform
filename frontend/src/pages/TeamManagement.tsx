import React, { useEffect, useState } from 'react';
import { Users, UserPlus, Shield, ShieldAlert, Check } from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { Member } from '../types';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

export const TeamManagement: React.FC = () => {
  const { role, organizationName } = useAuth();
  const [members, setMembers] = useState<Member[]>([]);
  const [fullName, setFullName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newRole, setNewRole] = useState('knowledge_reviewer');
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const isAdmin = role === 'org_admin';

  const loadMembers = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const list = await api.getMembers();
      setMembers(list);
    } catch (err) {
      console.error('Failed to load members:', err);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    loadMembers(false);
  }, []);

  useAutoRefresh(() => {
    if (!submitting) {
      loadMembers(true);
    }
  }, { intervalMs: 6000 });

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail) return;
    setSubmitting(true);
    setStatusMessage(null);
    try {
      await api.addMember({
        user_email: newEmail,
        role: newRole,
        full_name: fullName.trim() || undefined,
        password: password || undefined,
      });
      setStatusMessage({
        type: 'success',
        text: `Team member '${newEmail}' provisioned successfully with role '${newRole.replace('_', ' ')}'.`
      });
      setFullName('');
      setNewEmail('');
      setPassword('');
      await loadMembers();
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: err.message || 'Failed to provision member.'
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 className="title-xl">Team & Role-Based Permissions</h1>
        <p className="text-sub">
          Manage workspace members across the 4 governance roles: Org Admin, Knowledge Reviewer, Content Creator, and Approval Manager.
        </p>
      </div>

      {!isAdmin && (
        <div style={{ padding: '12px 18px', background: 'rgba(99, 102, 241, 0.08)', borderRadius: 10, border: '1px solid rgba(99, 102, 241, 0.25)', marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
          <ShieldAlert size={20} color="#818cf8" />
          <div style={{ fontSize: '0.82rem', color: '#c7d2fe' }}>
            <strong>Viewing with role '{role}':</strong> Role administration is restricted to <strong>Organization Administrator</strong> (Alice Administrator). Switch personas in the top-right menu to manage members.
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 24 }}>
        {/* Members List */}
        <div className="card">
          <h2 className="title-md" style={{ marginBottom: 16 }}>
            Active Organization Members ({members.length})
          </h2>

          {loading ? (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-dim)' }}>Loading members...</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {members.map((m) => (
                <div
                  key={m.id}
                  style={{
                    padding: '12px 16px',
                    borderRadius: 8,
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{
                      width: 36,
                      height: 36,
                      borderRadius: '50%',
                      background: 'rgba(99,102,241,0.2)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      color: '#a5b4fc',
                      fontSize: '0.85rem'
                    }}>
                      {m.user_full_name.charAt(0)}
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.9rem' }}>
                        {m.user_full_name}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                        {m.user_email}
                      </div>
                    </div>
                  </div>

                  <span className="badge badge-neutral" style={{ textTransform: 'capitalize' }}>
                    {m.role.replace('_', ' ')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Provision Member Card */}
        <div className="card">
          <h2 className="title-md" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <UserPlus size={18} color="#818cf8" /> Provision Team Member
          </h2>

          {statusMessage && (
            <div style={{
              padding: '10px 14px',
              borderRadius: 8,
              fontSize: '0.82rem',
              marginBottom: 16,
              background: statusMessage.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
              border: `1px solid ${statusMessage.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
              color: statusMessage.type === 'success' ? '#34d399' : '#fb7185'
            }}>
              {statusMessage.text}
            </div>
          )}

          <form onSubmit={handleAddMember}>
            <div className="form-group">
              <label className="form-label">Full Name</label>
              <input
                type="text"
                placeholder="e.g. Rachel Reviewer"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="input"
                disabled={!isAdmin}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Work Email</label>
              <input
                type="email"
                placeholder="e.g. reviewer@solisbrews.demo"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className="input"
                disabled={!isAdmin}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Assigned Governance Role</label>
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
                className="select"
                disabled={!isAdmin}
              >
                <option value="knowledge_reviewer">Knowledge Reviewer</option>
                <option value="content_creator">Content Creator</option>
                <option value="approval_manager">Approval Manager</option>
              </select>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 4, display: 'block' }}>
                Org Admin role cannot be provisioned through this form.
              </span>
            </div>

            <div className="form-group">
              <label className="form-label">Initial Password</label>
              <input
                type="password"
                placeholder="Minimum 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                disabled={!isAdmin}
                minLength={8}
                required
              />
            </div>

            <button type="submit" disabled={!isAdmin || submitting} className="btn btn-primary" style={{ width: '100%', marginTop: 8 }}>
              {submitting ? 'Provisioning...' : 'Provision Member'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
