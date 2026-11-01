import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import {
  ShieldCheck,
  Building2,
  Lock,
  User,
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Mail
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { InvitationVerifyData } from '../types';

export const AcceptInvitation: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { setSessionFromTokenResponse } = useAuth();

  const token = searchParams.get('token') || '';

  const [verifying, setVerifying] = useState(true);
  const [invitationData, setInvitationData] = useState<InvitationVerifyData | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  // Form State
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    const verify = async () => {
      if (!token) {
        setVerifyError('No invitation token was provided in the URL.');
        setVerifying(false);
        return;
      }

      try {
        setVerifying(true);
        setVerifyError(null);
        const data = await api.verifyInvitation(token);
        setInvitationData(data);
      } catch (err: any) {
        setVerifyError(err.message || 'Invitation link is invalid, expired, or revoked.');
      } finally {
        setVerifying(false);
      }
    };

    verify();
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!invitationData?.is_existing_user) {
      if (!fullName.trim() || fullName.trim().length < 2) {
        setSubmitError('Full name is required (minimum 2 characters).');
        return;
      }
      if (password.length < 8) {
        setSubmitError('Password must be at least 8 characters long.');
        return;
      }
      if (password !== confirmPassword) {
        setSubmitError('Passwords do not match.');
        return;
      }
    } else {
      if (!password) {
        setSubmitError('Please enter your account password.');
        return;
      }
    }

    setSubmitting(true);
    try {
      const res = await api.acceptInvitation({
        token,
        full_name: invitationData?.is_existing_user ? undefined : fullName.trim(),
        password: password
      });

      setSuccess(true);
      setSessionFromTokenResponse(res);

      setTimeout(() => {
        navigate('/');
      }, 1000);
    } catch (err: any) {
      setSubmitError(err.message || 'Failed to accept invitation. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'radial-gradient(circle at 50% 15%, #1e1b4b 0%, #090d16 70%)',
        padding: '40px 20px'
      }}
    >
      <div style={{ width: '100%', maxWidth: 520 }}>
        {/* Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div
            style={{
              width: 54,
              height: 54,
              borderRadius: 16,
              background: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 10px 25px -5px rgba(99, 102, 241, 0.5)',
              marginBottom: 14
            }}
          >
            <ShieldCheck size={32} color="#ffffff" />
          </div>
          <h1
            style={{
              fontSize: '1.75rem',
              fontWeight: 800,
              color: '#ffffff',
              letterSpacing: '-0.025em',
              margin: '0 0 6px 0'
            }}
          >
            Inkloom<span style={{ color: '#818cf8' }}>.AI</span>
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.88rem', margin: 0 }}>
            Brand Governance & Content Integrity Platform
          </p>
        </div>

        {/* Card Container */}
        <div
          className="card"
          style={{
            backgroundColor: '#0f172a',
            border: '1px solid rgba(99, 102, 241, 0.25)',
            borderRadius: 16,
            padding: 32,
            boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.8)'
          }}
        >
          {verifying ? (
            <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-dim)' }}>
              <RefreshCw size={28} className="spin" style={{ margin: '0 auto 12px', color: '#818cf8' }} />
              <div style={{ color: '#fff', fontWeight: 600 }}>Verifying workspace invitation...</div>
            </div>
          ) : verifyError ? (
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <div
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: '50%',
                  background: 'rgba(239, 68, 68, 0.15)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#ef4444',
                  marginBottom: 16
                }}
              >
                <AlertTriangle size={26} />
              </div>
              <h2 style={{ fontSize: '1.15rem', color: '#fff', marginBottom: 8 }}>
                Invitation Invalid or Expired
              </h2>
              <p style={{ color: '#f87171', fontSize: '0.85rem', marginBottom: 24 }}>
                {verifyError}
              </p>
              <Link to="/login" className="btn btn-secondary" style={{ display: 'inline-block' }}>
                Return to Sign In
              </Link>
            </div>
          ) : invitationData ? (
            <div>
              {/* Workspace Badge Header */}
              <div
                style={{
                  padding: 16,
                  borderRadius: 12,
                  background: 'rgba(99, 102, 241, 0.08)',
                  border: '1px solid rgba(99, 102, 241, 0.25)',
                  marginBottom: 24,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 14
                }}
              >
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 10,
                    background: 'rgba(99, 102, 241, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#818cf8'
                  }}
                >
                  <Building2 size={24} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Workspace Invitation
                  </div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff' }}>
                    {invitationData.organization_name}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                    <span className="badge badge-neutral" style={{ textTransform: 'capitalize' }}>
                      {invitationData.role.replace('_', ' ')}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                      Expires {new Date(invitationData.expires_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>

              {submitError && (
                <div
                  style={{
                    padding: '12px 16px',
                    borderRadius: 8,
                    background: 'rgba(239, 68, 68, 0.15)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    color: '#f87171',
                    fontSize: '0.85rem',
                    marginBottom: 20,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10
                  }}
                >
                  <AlertTriangle size={18} />
                  <span>{submitError}</span>
                </div>
              )}

              {success ? (
                <div style={{ textAlign: 'center', padding: '24px 0' }}>
                  <CheckCircle2 size={40} color="#34d399" style={{ margin: '0 auto 12px' }} />
                  <h3 style={{ color: '#fff', fontSize: '1.1rem', marginBottom: 6 }}>
                    Invitation Accepted!
                  </h3>
                  <p style={{ color: 'var(--text-dim)', fontSize: '0.85rem' }}>
                    Redirecting you to the workspace dashboard...
                  </p>
                </div>
              ) : (
                <form onSubmit={handleSubmit}>
                  <div className="form-group" style={{ marginBottom: 16 }}>
                    <label className="form-label">Invited Work Email</label>
                    <div style={{ position: 'relative' }}>
                      <input
                        type="email"
                        value={invitationData.email}
                        disabled
                        className="input"
                        style={{ paddingLeft: 38, opacity: 0.8, cursor: 'not-allowed' }}
                      />
                      <Mail
                        size={18}
                        color="var(--text-dim)"
                        style={{ position: 'absolute', left: 12, top: 12 }}
                      />
                    </div>
                  </div>

                  {!invitationData.is_existing_user && (
                    <div className="form-group" style={{ marginBottom: 16 }}>
                      <label className="form-label">Your Full Name</label>
                      <div style={{ position: 'relative' }}>
                        <input
                          type="text"
                          placeholder="e.g. Rachel Reviewer"
                          value={fullName}
                          onChange={(e) => setFullName(e.target.value)}
                          className="input"
                          style={{ paddingLeft: 38 }}
                          required
                        />
                        <User
                          size={18}
                          color="var(--text-dim)"
                          style={{ position: 'absolute', left: 12, top: 12 }}
                        />
                      </div>
                    </div>
                  )}

                  <div className="form-group" style={{ marginBottom: 16 }}>
                    <label className="form-label">
                      {invitationData.is_existing_user ? 'Account Password' : 'Create Password'}
                    </label>
                    <div style={{ position: 'relative' }}>
                      <input
                        type="password"
                        placeholder={invitationData.is_existing_user ? 'Enter your existing password' : 'At least 8 characters'}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="input"
                        style={{ paddingLeft: 38 }}
                        required
                        minLength={8}
                      />
                      <Lock
                        size={18}
                        color="var(--text-dim)"
                        style={{ position: 'absolute', left: 12, top: 12 }}
                      />
                    </div>
                  </div>

                  {!invitationData.is_existing_user && (
                    <div className="form-group" style={{ marginBottom: 20 }}>
                      <label className="form-label">Confirm Password</label>
                      <div style={{ position: 'relative' }}>
                        <input
                          type="password"
                          placeholder="Re-enter password"
                          value={confirmPassword}
                          onChange={(e) => setConfirmPassword(e.target.value)}
                          className="input"
                          style={{ paddingLeft: 38 }}
                          required
                          minLength={8}
                        />
                        <Lock
                          size={18}
                          color="var(--text-dim)"
                          style={{ position: 'absolute', left: 12, top: 12 }}
                        />
                      </div>
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={submitting}
                    className="btn btn-primary"
                    style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
                  >
                    {submitting ? (
                      <>
                        <RefreshCw size={16} className="spin" /> Joining Workspace...
                      </>
                    ) : (
                      <>
                        Accept & Enter Workspace <ArrowRight size={16} />
                      </>
                    )}
                  </button>
                </form>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};
