import React, { useEffect, useState } from 'react';
import {
  Users,
  UserPlus,
  Shield,
  ShieldAlert,
  Check,
  Mail,
  Copy,
  RotateCw,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Send,
  Clock,
  ExternalLink
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { Member, OrganizationInvitation, UserRole } from '../types';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

export const TeamManagement: React.FC = () => {
  const { role, organizationId, organizationName } = useAuth();
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<OrganizationInvitation[]>([]);

  // Direct provision form state
  const [fullName, setFullName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newRole, setNewRole] = useState('knowledge_reviewer');

  // Invitation modal state
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteName, setInviteName] = useState('');
  const [inviteRole, setInviteRole] = useState<UserRole>('content_creator');
  const [inviting, setInviting] = useState(false);
  const [latestInviteLink, setLatestInviteLink] = useState<string | null>(null);

  // General UI state
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [copiedTokenId, setCopiedTokenId] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const isAdmin = role === 'org_admin';

  const loadData = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const list = await api.getMembers();
      setMembers(list);

      if (isAdmin && organizationId) {
        const invs = await api.getInvitations(organizationId);
        setInvitations(invs);
      }
    } catch (err) {
      console.error('Failed to load team data:', err);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    loadData(false);
  }, [organizationId, isAdmin]);

  useAutoRefresh(() => {
    if (!submitting && !inviting) {
      loadData(true);
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
      await loadData();
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: err.message || 'Failed to provision member.'
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSendInvitation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!organizationId || !inviteEmail.trim()) return;

    setInviting(true);
    setStatusMessage(null);
    try {
      const inv = await api.createInvitation(organizationId, inviteEmail.trim(), inviteRole, inviteName.trim() || undefined);
      setStatusMessage({
        type: 'success',
        text: `Invitation created for ${inv.email} with role '${inv.role.replace('_', ' ')}'.`
      });
      if (inv.invitation_link) {
        setLatestInviteLink(inv.invitation_link);
      }
      setInviteEmail('');
      setInviteName('');
      await loadData();
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: err.message || 'Failed to create invitation.'
      });
    } finally {
      setInviting(false);
    }
  };

  const handleResend = async (invitationId: string) => {
    if (!organizationId) return;
    try {
      const inv = await api.resendInvitation(organizationId, invitationId);
      setStatusMessage({
        type: 'success',
        text: `Invitation resent to ${inv.email} with rotated security token.`
      });
      if (inv.invitation_link) {
        navigator.clipboard.writeText(inv.invitation_link);
        setCopiedTokenId(invitationId);
        setTimeout(() => setCopiedTokenId(null), 3000);
      }
      await loadData();
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: err.message || 'Failed to resend invitation.'
      });
    }
  };

  const handleRevoke = async (invitationId: string) => {
    if (!organizationId) return;
    try {
      await api.revokeInvitation(organizationId, invitationId);
      setStatusMessage({
        type: 'success',
        text: 'Invitation revoked successfully.'
      });
      await loadData();
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: err.message || 'Failed to revoke invitation.'
      });
    }
  };

  const handleCopyLink = (link: string, id: string) => {
    navigator.clipboard.writeText(link);
    setCopiedTokenId(id);
    setTimeout(() => setCopiedTokenId(null), 3000);
  };

  return (
    <div>
      <div style={{ marginBottom: 24, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 className="title-xl">Team & Governance Role Access</h1>
          <p className="text-sub">
            Manage organization members and secure token-based invitations across the 4 governance roles
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={() => {
              setShowInviteModal(true);
              setLatestInviteLink(null);
            }}
            className="btn btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            <Mail size={16} /> Invite Team Member
          </button>
        )}
      </div>

      {!isAdmin && (
        <div style={{ padding: '12px 18px', background: 'rgba(99, 102, 241, 0.08)', borderRadius: 10, border: '1px solid rgba(99, 102, 241, 0.25)', marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
          <ShieldAlert size={20} color="#818cf8" />
          <div style={{ fontSize: '0.82rem', color: '#c7d2fe' }}>
            <strong>Viewing with role '{role}':</strong> Role administration and member invitations are restricted to <strong>Organization Administrator</strong>. Switch personas in the top-right menu to manage access.
          </div>
        </div>
      )}

      {statusMessage && (
        <div style={{
          padding: '12px 16px',
          borderRadius: 8,
          fontSize: '0.85rem',
          marginBottom: 20,
          background: statusMessage.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
          border: `1px solid ${statusMessage.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
          color: statusMessage.type === 'success' ? '#34d399' : '#fb7185',
          display: 'flex',
          alignItems: 'center',
          gap: 10
        }}>
          {statusMessage.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span>{statusMessage.text}</span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 24 }}>
        {/* Left Column: Active Members & Pending Invitations */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Active Members Table */}
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

          {/* Pending Invitations Section */}
          {isAdmin && (
            <div className="card">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div>
                  <h2 className="title-md" style={{ margin: 0 }}>
                    Workspace Invitations ({invitations.length})
                  </h2>
                  <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    Cryptographically secured invitation tokens with automatic expiry and zero-billing delivery fallback
                  </p>
                </div>
              </div>

              {invitations.length === 0 ? (
                <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-dim)', fontSize: '0.85rem' }}>
                  No pending or historical invitations found. Use the "Invite Team Member" button above to send an invitation.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {invitations.map((inv) => {
                    const isPending = inv.status === 'pending';
                    const isAccepted = inv.status === 'accepted';
                    const isRevoked = inv.status === 'revoked';

                    return (
                      <div
                        key={inv.id}
                        style={{
                          padding: 14,
                          borderRadius: 8,
                          background: isPending ? 'rgba(99, 102, 241, 0.04)' : 'rgba(255, 255, 255, 0.01)',
                          border: `1px solid ${isPending ? 'rgba(99, 102, 241, 0.2)' : 'var(--border-subtle)'}`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between'
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontWeight: 600, color: '#fff', fontSize: '0.9rem' }}>
                              {inv.email}
                            </span>
                            <span className="badge badge-neutral" style={{ textTransform: 'capitalize', fontSize: '0.72rem' }}>
                              {inv.role.replace('_', ' ')}
                            </span>
                            {isPending && (
                              <span className="badge badge-warning" style={{ fontSize: '0.72rem' }}>
                                Pending
                              </span>
                            )}
                            {isAccepted && (
                              <span className="badge badge-success" style={{ fontSize: '0.72rem' }}>
                                Accepted
                              </span>
                            )}
                            {isRevoked && (
                              <span className="badge badge-error" style={{ fontSize: '0.72rem' }}>
                                Revoked
                              </span>
                            )}
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginTop: 4, fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                            <span>Invited by: {inv.inviter_email_snapshot}</span>
                            <span>Expires: {new Date(inv.expires_at).toLocaleDateString()}</span>
                            {inv.delivery_status === 'unconfigured_demo_fallback' && (
                              <span style={{ color: '#fbbf24' }}>
                                Demo mode (link copy ready)
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Actions */}
                        {isPending && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <button
                              onClick={() => handleResend(inv.id)}
                              className="btn btn-secondary"
                              title="Rotate token and refresh expiry"
                              style={{ padding: '6px 10px', fontSize: '0.78rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                            >
                              <RotateCw size={13} /> {copiedTokenId === inv.id ? 'Copied New Link!' : 'Resend'}
                            </button>
                            <button
                              onClick={() => handleRevoke(inv.id)}
                              className="btn btn-secondary"
                              title="Revoke invitation"
                              style={{ padding: '6px 10px', fontSize: '0.78rem', color: '#f87171' }}
                            >
                              <Trash2 size={13} /> Revoke
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Direct Admin Provision Form */}
        <div className="card" style={{ height: 'fit-content' }}>
          <h2 className="title-md" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <UserPlus size={18} color="#818cf8" /> Direct Account Provision
          </h2>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginBottom: 16 }}>
            Directly create credentials for a team member without email verification.
          </p>

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
                Org Admin role must be invited via secure invitation link.
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

      {/* Invite Member Modal */}
      {showInviteModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: 20
          }}
        >
          <div
            className="card"
            style={{
              width: '100%',
              maxWidth: 520,
              backgroundColor: '#0f172a',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              borderRadius: 16,
              padding: 24,
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 36, height: 36, borderRadius: 8, background: 'rgba(99,102,241,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#818cf8' }}>
                  <Mail size={18} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#fff' }}>Invite Team Member</h3>
                  <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    Generate a single-use 7-day secure onboarding link
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowInviteModal(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            {latestInviteLink ? (
              <div style={{ padding: '16px 0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#34d399', marginBottom: 12 }}>
                  <CheckCircle2 size={20} />
                  <span style={{ fontWeight: 600 }}>Invitation Link Generated!</span>
                </div>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-dim)', marginBottom: 12 }}>
                  Because external email delivery is running in zero-billing fallback mode, copy and share this link directly with the invitee:
                </p>

                <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
                  <input
                    type="text"
                    value={latestInviteLink}
                    readOnly
                    className="input"
                    style={{ fontSize: '0.78rem', color: '#a5b4fc', background: 'rgba(0,0,0,0.3)' }}
                  />
                  <button
                    onClick={() => handleCopyLink(latestInviteLink, 'modal')}
                    className="btn btn-primary"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}
                  >
                    <Copy size={14} /> {copiedTokenId === 'modal' ? 'Copied!' : 'Copy Link'}
                  </button>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                  <button
                    onClick={() => setLatestInviteLink(null)}
                    className="btn btn-secondary"
                  >
                    Invite Another
                  </button>
                  <button
                    onClick={() => setShowInviteModal(false)}
                    className="btn btn-primary"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSendInvitation}>
                <div className="form-group" style={{ marginBottom: 14 }}>
                  <label className="form-label">Recipient Email *</label>
                  <input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="e.g. colleague@company.com"
                    className="input"
                    required
                  />
                </div>

                <div className="form-group" style={{ marginBottom: 14 }}>
                  <label className="form-label">Invitee Name (Optional)</label>
                  <input
                    type="text"
                    value={inviteName}
                    onChange={(e) => setInviteName(e.target.value)}
                    placeholder="e.g. Marcus Manager"
                    className="input"
                  />
                </div>

                <div className="form-group" style={{ marginBottom: 20 }}>
                  <label className="form-label">Workspace Governance Role *</label>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as UserRole)}
                    className="select"
                  >
                    <option value="content_creator">Content Creator (Author drafts & view suggestions)</option>
                    <option value="knowledge_reviewer">Knowledge Reviewer (Review rules & approve facts)</option>
                    <option value="approval_manager">Approval Manager (Final publish & campaign sign-off)</option>
                    <option value="org_admin">Organization Administrator (Full workspace admin)</option>
                  </select>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                  <button
                    type="button"
                    onClick={() => setShowInviteModal(false)}
                    className="btn btn-secondary"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={inviting}
                    className="btn btn-primary"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
                  >
                    {inviting ? 'Generating...' : 'Create Invitation Link'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
