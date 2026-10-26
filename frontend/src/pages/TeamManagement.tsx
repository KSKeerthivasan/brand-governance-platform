import React, { useEffect, useState } from 'react';
import { Users, UserPlus, Shield, ShieldAlert, Check } from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { Member } from '../types';

export const TeamManagement: React.FC = () => {
  const { role, organizationName } = useAuth();
  const [members, setMembers] = useState<Member[]>([]);
  const [newEmail, setNewEmail] = useState('');
  const [newRole, setNewRole] = useState('content_creator');
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);

  const isAdmin = role === 'org_admin';

  const loadMembers = async () => {
    try {
      setLoading(true);
      const list = await api.getMembers();
      setMembers(list);
    } catch (err) {
      console.error('Failed to load members:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMembers();
  }, []);

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail) return;
    setSubmitting(true);
    try {
      await api.addMember(newEmail, newRole);
      alert(`Role '${newRole}' assigned to ${newEmail}`);
      setNewEmail('');
      await loadMembers();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
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

        {/* Add/Update Member Card */}
        <div className="card">
          <h2 className="title-md" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <UserPlus size={18} color="#818cf8" /> Assign Member Role
          </h2>

          <form onSubmit={handleAddMember}>
            <div className="form-group">
              <label className="form-label">User Email</label>
              <input
                type="email"
                placeholder="e.g. colleague@freshsip.demo"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className="input"
                disabled={!isAdmin}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Assigned Role</label>
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
                className="select"
                disabled={!isAdmin}
              >
                <option value="content_creator">Content Creator</option>
                <option value="knowledge_reviewer">Knowledge Reviewer</option>
                <option value="approval_manager">Approval Manager</option>
                <option value="org_admin">Organization Administrator</option>
              </select>
            </div>

            <button type="submit" disabled={!isAdmin || submitting} className="btn btn-primary" style={{ width: '100%', marginTop: 8 }}>
              {submitting ? 'Updating...' : 'Assign Role'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
