import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ShieldCheck, ArrowRight, UserCheck, Lock, Mail, Building2, Sparkles, RefreshCw, AlertCircle } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { UserRole } from '../types';

export const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [orgSlug, setOrgSlug] = useState('');
  const [loading, setLoading] = useState(false);
  const [activePersona, setActivePersona] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [coldStartNotice, setColdStartNotice] = useState(false);

  // Seeded demo personas for one-click access
  const personas: { role: UserRole; name: string; email: string; label: string; desc: string }[] = [
    {
      role: 'content_creator',
      name: 'Chris Creator',
      email: 'creator@freshsip.demo',
      label: 'Content Creator',
      desc: 'Creates marketing copy, runs automated compliance checks, submits versions'
    },
    {
      role: 'knowledge_reviewer',
      name: 'Rachel Reviewer',
      email: 'reviewer@freshsip.demo',
      label: 'Knowledge Reviewer',
      desc: 'Inspects brand guidelines, verifies product facts, approves extracted rules'
    },
    {
      role: 'approval_manager',
      name: 'Marcus Manager',
      email: 'approver@freshsip.demo',
      label: 'Approval Manager',
      desc: 'Reviews candidate submissions, issues formal pre-publication sign-offs'
    },
    {
      role: 'org_admin',
      name: 'Alice Administrator',
      email: 'admin@freshsip.demo',
      label: 'Org Admin',
      desc: 'Workspace administration, team role assignments, and immutable audit logs'
    },
  ];

  // Cold start timer for friendly user feedback during Render spin-up
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    if (loading) {
      timer = setTimeout(() => {
        setColdStartNotice(true);
      }, 3500);
    } else {
      setColdStartNotice(false);
    }
    return () => clearTimeout(timer);
  }, [loading]);

  const handleStandardLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    setLoading(true);
    setActivePersona(null);
    setError(null);
    try {
      await login(email.trim(), password, undefined, orgSlug.trim() || undefined);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Login failed. Please verify your credentials and network connection.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickPersona = async (pEmail: string, pName: string) => {
    if (loading) return;
    setLoading(true);
    setActivePersona(pName);
    setError(null);
    try {
      // Authenticate directly through standard POST /api/v1/auth/login using public demo credentials
      await login(pEmail, 'Freshsip2026!', undefined, 'freshsip');
      navigate('/');
    } catch (err: any) {
      setError(err.message || `Failed to sign in as ${pName}. Please verify network connectivity.`);
    } finally {
      setLoading(false);
      setActivePersona(null);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'radial-gradient(circle at 50% 20%, #1e1b4b 0%, #090d16 60%)',
      padding: '24px 16px'
    }}>
      <div style={{
        width: '100%',
        maxWidth: 1000,
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
        gap: 28,
        alignItems: 'stretch'
      }}>
        {/* Left Column: One-Click Demo Access for Judges */}
        <div className="card" style={{
          padding: 28,
          background: 'rgba(19, 27, 46, 0.75)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(99, 102, 241, 0.3)',
          display: 'flex',
          flexDirection: 'column'
        }}>
          {/* Brand Logo & Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <div style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 20px rgba(99, 102, 241, 0.5)'
            }}>
              <ShieldCheck size={26} color="#fff" />
            </div>
            <div>
              <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
                Inkloom<span style={{ color: '#6366f1' }}>.AI</span>
              </div>
              <div style={{ fontSize: '0.8rem', color: '#a5b4fc', fontWeight: 600 }}>Brand Governance Workspace</div>
            </div>
          </div>

          {/* Section Heading & Demo Notice */}
          <div style={{ marginBottom: 18 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span className="badge badge-info" style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Demo Access
              </span>
              <span style={{ fontSize: '0.72rem', color: '#10b981', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <Sparkles size={12} /> 1-Click Evaluation
              </span>
            </div>
            <h2 className="title-md" style={{ marginBottom: 4 }}>
              Select a Demo Persona
            </h2>
            <p className="text-sub" style={{ fontSize: '0.8rem', lineHeight: 1.5, color: '#94a3b8' }}>
              Instant one-click access for product evaluation. Authenticates into the synthetic <strong>Freshsip Beverage Co.</strong> demonstration workspace:
            </p>
          </div>

          {/* Persona Selection Cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, flex: 1 }}>
            {personas.map((p) => {
              const isThisLoading = loading && activePersona === p.name;
              return (
                <button
                  key={p.role}
                  type="button"
                  onClick={() => handleQuickPersona(p.email, p.name)}
                  disabled={loading}
                  className="card card-hoverable"
                  style={{
                    padding: '12px 14px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    textAlign: 'left',
                    background: isThisLoading ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                    border: isThisLoading ? '1px solid #818cf8' : '1px solid var(--border-subtle)',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    width: '100%',
                    opacity: loading && !isThisLoading ? 0.6 : 1,
                    transition: 'all 0.15s ease'
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0, paddingRight: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                      <span style={{ fontWeight: 700, color: '#fff', fontSize: '0.875rem' }}>
                        {p.name}
                      </span>
                      <span className="badge" style={{
                        fontSize: '0.65rem',
                        padding: '1px 6px',
                        background: 'rgba(99, 102, 241, 0.18)',
                        color: '#a5b4fc',
                        border: '1px solid rgba(99, 102, 241, 0.35)'
                      }}>
                        {p.label}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#94a3b8', lineHeight: 1.4 }}>
                      {p.desc}
                    </div>
                  </div>
                  <div>
                    {isThisLoading ? (
                      <RefreshCw size={16} className="spin" color="#818cf8" />
                    ) : (
                      <ArrowRight size={16} color="#818cf8" />
                    )}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Active Loading & Cold-Start Status Feedback */}
          {loading && activePersona && (
            <div style={{
              marginTop: 14,
              padding: '8px 12px',
              borderRadius: 6,
              background: 'rgba(99, 102, 241, 0.12)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              fontSize: '0.78rem',
              color: '#c7d2fe',
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}>
              <RefreshCw size={14} className="spin" color="#818cf8" />
              <div>
                Authenticating as <strong>{activePersona}</strong>...
                {coldStartNotice && (
                  <div style={{ fontSize: '0.72rem', color: '#fde047', marginTop: 2 }}>
                    Backend waking up from standby (Render free tier). Please allow up to 10-15s.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Synthetic Demo Data Disclaimer */}
          <div style={{ marginTop: 14, paddingTop: 10, borderTop: '1px solid var(--border-subtle)', fontSize: '0.7rem', color: '#64748b' }}>
            Note: Demo accounts contain synthetic compliance rules and sample assets for testing. Public demo credentials are non-sensitive and reset-safe.
          </div>
        </div>

        {/* Right Column: Standard Email/Password Form */}
        <div className="card" style={{
          padding: 28,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          background: 'rgba(19, 27, 46, 0.65)'
        }}>
          <h2 className="title-lg" style={{ marginBottom: 4 }}>Standard Sign In</h2>
          <p className="text-sub" style={{ marginBottom: 20, fontSize: '0.8rem' }}>
            Sign in with email and password, or access a custom organization:
          </p>

          <form onSubmit={handleStandardLogin}>
            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Mail size={14} /> Email Address
              </label>
              <input
                type="email"
                placeholder="creator@freshsip.demo"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                disabled={loading}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Lock size={14} /> Password
              </label>
              <input
                type="password"
                placeholder="Freshsip2026!"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                disabled={loading}
                required
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 4 }}>
                Seeded demo password: <code>Freshsip2026!</code>
              </span>
            </div>

            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Building2 size={14} /> Workspace Slug <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>(Optional)</span>
              </label>
              <input
                type="text"
                placeholder="e.g. freshsip or nexoratech"
                value={orgSlug}
                onChange={(e) => setOrgSlug(e.target.value)}
                className="input"
                disabled={loading}
              />
            </div>

            {error && (
              <div style={{
                padding: '10px 12px',
                borderRadius: 6,
                background: 'rgba(244,63,94,0.15)',
                border: '1px solid rgba(244,63,94,0.3)',
                color: '#fb7185',
                fontSize: '0.8rem',
                marginBottom: 14,
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8
              }}>
                <AlertCircle size={16} style={{ flexShrink: 0, marginTop: 1 }} />
                <div>{error}</div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary"
              style={{ width: '100%', marginTop: 6, padding: '10px 16px', fontSize: '0.875rem' }}
            >
              {loading && !activePersona ? (
                <>
                  <RefreshCw size={14} className="spin" />
                  Authenticating...
                </>
              ) : (
                'Sign In with Email'
              )}
            </button>

            <div style={{ marginTop: 22, paddingTop: 16, borderTop: '1px solid var(--border-subtle)', textAlign: 'center' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Need an isolated workspace? </span>
              <Link to="/onboarding" style={{ fontSize: '0.82rem', color: '#818cf8', fontWeight: 600, textDecoration: 'none' }}>
                Onboard new organization →
              </Link>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
