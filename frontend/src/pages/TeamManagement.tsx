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

  // Invitation modal state
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteName, setInviteName] = useState('');
  const [inviteRole, setInviteRole] = useState<UserRole>('content_creator');
  const [inviting, setInviting] = useState(false);
  const [latestInvite, setLatestInvite] = useState<OrganizationInvitation | null>(null);

  // General UI state
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
    if (!inviting) {
      loadData(true);
    }
  }, { intervalMs: 6000 });

  const handleSendInvitation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!organizationId || !inviteEmail.trim()) return;

    setInviting(true);
    setStatusMessage(null);
    try {
      const inv = await api.createInvitation(organizationId, inviteEmail.trim(), inviteRole, inviteName.trim() || undefined);
      setLatestInvite(inv);
      if (inv.delivery_status === 'sent') {
        setStatusMessage({
          type: 'success',
          text: `Invitation dispatched via Gmail SMTP to ${inv.email} with role '${inv.role.replace('_', ' ')}'.`
        });
      } else if (inv.delivery_status === 'failed') {
        setStatusMessage({
          type: 'error',
          text: `SMTP delivery failed for ${inv.email}. Manual invitation link generated.`
        });
      } else {
        setStatusMessage({
          type: 'success',
          text: `Invitation created for ${inv.email} (demo fallback link ready).`
        });
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
      if (inv.delivery_status === 'sent') {
        setStatusMessage({
          type: 'success',
          text: `Invitation email re-dispatched via SMTP to ${inv.email} with rotated security token.`
        });
      } else if (inv.delivery_status === 'failed') {
        setStatusMessage({
          type: 'error',
          text: `SMTP delivery failed for ${inv.email}. Rotated single-use link copied to clipboard.`
        });
      } else {
        setStatusMessage({
          type: 'success',
          text: `Rotated single-use invitation link for ${inv.email} copied to clipboard.`
        });
      }
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
              setLatestInvite(null);
            }}
            className="btn btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            <Mail size={16} /> Invite Team Member
          </button>
        )}
      </div>

      {!isAdmin && (
        <div style={{ padding: '12px 18px', background: 'rgba(34, 197, 94, 0.08)', borderRadius: 10, border: '1px solid rgba(99, 102, 241, 0.25)', marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
          <ShieldAlert size={20} color="#4ade80" />
          <div style={{ fontSize: '0.82rem', color: '#f0fdf4' }}>
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
                      background: 'rgba(34, 197, 94, 0.15)',
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

        {/* Pending & Historical Invitations Section */}
        {isAdmin && (
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div>
                <h2 className="title-md" style={{ margin: 0 }}>
                  Workspace Invitations ({invitations.length})
                </h2>
                <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                  Cryptographically secured single-use invitation tokens with 7-day expiry and Gmail SMTP delivery
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
                        background: isPending ? 'rgba(34, 197, 94, 0.04)' : 'rgba(255, 255, 255, 0.01)',
                        border: `1px solid ${isPending ? 'rgba(34, 197, 94, 0.2)' : 'var(--border-subtle)'}`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between'
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
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

                          {/* Delivery status badge */}
                          {inv.delivery_status === 'sent' && (
                            <span className="badge badge-success" style={{ fontSize: '0.72rem' }}>
                              Sent via SMTP
                            </span>
                          )}
                          {inv.delivery_status === 'unconfigured_demo_fallback' && (
                            <span className="badge badge-warning" style={{ fontSize: '0.72rem' }}>
                              Demo Fallback
                            </span>
                          )}
                          {inv.delivery_status === 'failed' && (
                            <span className="badge badge-error" style={{ fontSize: '0.72rem' }}>
                              SMTP Delivery Failed
                            </span>
                          )}
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginTop: 4, fontSize: '0.75rem', color: 'var(--text-dim)', flexWrap: 'wrap' }}>
                          <span>Invited by: {inv.inviter_email_snapshot}</span>
                          <span>Expires: {new Date(inv.expires_at).toLocaleDateString()}</span>
                          {inv.delivery_status === 'sent' && (
                            <span style={{ color: '#34d399' }}>
                              Delivered via Gmail SMTP
                            </span>
                          )}
                          {inv.delivery_status === 'unconfigured_demo_fallback' && (
                            <span style={{ color: '#fbbf24' }}>
                              SMTP unconfigured (manual link ready)
                            </span>
                          )}
                          {inv.delivery_status === 'failed' && (
                            <span style={{ color: '#f87171' }}>
                              SMTP delivery error (share direct link)
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
              backgroundColor: '#0c100e',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 16,
              padding: 24,
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 36, height: 36, borderRadius: 8, background: 'rgba(34, 197, 94, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#4ade80' }}>
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

            {latestInvite ? (
              <div style={{ padding: '16px 0' }}>
                {latestInvite.delivery_status === 'sent' && (
                  <>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#34d399', marginBottom: 12 }}>
                      <CheckCircle2 size={22} />
                      <span style={{ fontWeight: 700, fontSize: '1.05rem', color: '#fff' }}>
                        Invitation Dispatched via Gmail SMTP
                      </span>
                    </div>
                    <p style={{ fontSize: '0.84rem', color: '#cbd5e1', marginBottom: 16, lineHeight: 1.5 }}>
                      An official invitation email has been dispatched to <strong style={{ color: '#fff' }}>{latestInvite.email}</strong> via Gmail SMTP. The recipient can click the secure link in their inbox to establish their password and join as <strong style={{ color: '#a5b4fc' }}>{latestInvite.role.replace('_', ' ')}</strong>.
                    </p>

                    <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12, marginBottom: 20 }}>
                      <div style={{ fontSize: '0.74rem', color: 'var(--text-dim)', marginBottom: 6 }}>
                        Direct Invitation Link (Backup for immediate access):
                      </div>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <input
                          type="text"
                          value={latestInvite.invitation_link || ''}
                          readOnly
                          className="input"
                          style={{ fontSize: '0.78rem', color: '#a5b4fc', background: 'rgba(0,0,0,0.3)' }}
                        />
                        <button
                          onClick={() => handleCopyLink(latestInvite.invitation_link || '', 'modal')}
                          className="btn btn-secondary"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap', fontSize: '0.78rem' }}
                        >
                          <Copy size={13} /> {copiedTokenId === 'modal' ? 'Copied!' : 'Copy Link'}
                        </button>
                      </div>
                    </div>
                  </>
                )}

                {latestInvite.delivery_status === 'unconfigured_demo_fallback' && (
                  <>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#fbbf24', marginBottom: 12 }}>
                      <AlertCircle size={22} />
                      <span style={{ fontWeight: 700, fontSize: '1.05rem', color: '#fff' }}>
                        Single-Use Invitation Link Ready
                      </span>
                    </div>
                    <p style={{ fontSize: '0.84rem', color: '#cbd5e1', marginBottom: 16, lineHeight: 1.5 }}>
                      Because external email delivery is running in unconfigured demo fallback mode (<code style={{ color: '#fbbf24' }}>SMTP_EMAIL</code> / <code style={{ color: '#fbbf24' }}>SMTP_PASSWORD</code> unset in environment), copy and share this single-use link directly with <strong style={{ color: '#fff' }}>{latestInvite.email}</strong>:
                    </p>

                    <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
                      <input
                        type="text"
                        value={latestInvite.invitation_link || ''}
                        readOnly
                        className="input"
                        style={{ fontSize: '0.78rem', color: '#a5b4fc', background: 'rgba(0,0,0,0.3)' }}
                      />
                      <button
                        onClick={() => handleCopyLink(latestInvite.invitation_link || '', 'modal')}
                        className="btn btn-primary"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}
                      >
                        <Copy size={14} /> {copiedTokenId === 'modal' ? 'Copied!' : 'Copy Link'}
                      </button>
                    </div>
                  </>
                )}

                {latestInvite.delivery_status === 'failed' && (
                  <>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#f87171', marginBottom: 12 }}>
                      <AlertCircle size={22} />
                      <span style={{ fontWeight: 700, fontSize: '1.05rem', color: '#fff' }}>
                        SMTP Delivery Failed — Direct Link Ready
                      </span>
                    </div>
                    <p style={{ fontSize: '0.84rem', color: '#cbd5e1', marginBottom: 16, lineHeight: 1.5 }}>
                      Email dispatch to <strong style={{ color: '#fff' }}>{latestInvite.email}</strong> could not be completed via SMTP (connection or authentication error). The invitation has been securely created with a 7-day single-use token. Please copy and share this direct onboarding link with the invitee:
                    </p>

                    <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
                      <input
                        type="text"
                        value={latestInvite.invitation_link || ''}
                        readOnly
                        className="input"
                        style={{ fontSize: '0.78rem', color: '#a5b4fc', background: 'rgba(0,0,0,0.3)' }}
                      />
                      <button
                        onClick={() => handleCopyLink(latestInvite.invitation_link || '', 'modal')}
                        className="btn btn-primary"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}
                      >
                        <Copy size={14} /> {copiedTokenId === 'modal' ? 'Copied!' : 'Copy Link'}
                      </button>
                    </div>
                  </>
                )}

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                  <button
                    onClick={() => setLatestInvite(null)}
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
                    {inviting ? 'Generating...' : 'Send Invitation'}
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
