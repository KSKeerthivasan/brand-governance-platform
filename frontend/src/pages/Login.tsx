import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, ArrowRight, UserCheck, Lock, Mail } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { UserRole } from '../types';

export const Login: React.FC = () => {
  const { login, switchPersona } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const personas: { role: UserRole; name: string; email: string; label: string; desc: string }[] = [
    {
      role: 'content_creator',
      name: 'Chris Creator',
      email: 'creator@freshsip.demo',
      label: 'Content Creator',
      desc: 'Authors marketing copy, runs checks, submits drafts'
    },
    {
      role: 'knowledge_reviewer',
      name: 'Rachel Reviewer',
      email: 'reviewer@freshsip.demo',
      label: 'Knowledge Reviewer',
      desc: 'Inspects candidate brand guidelines, approves facts'
    },
    {
      role: 'approval_manager',
      name: 'Marcus Manager',
      email: 'approver@freshsip.demo',
      label: 'Approval Manager',
      desc: 'Evaluates submissions, issues publication sign-off'
    },
    {
      role: 'org_admin',
      name: 'Alice Administrator',
      email: 'admin@freshsip.demo',
      label: 'Org Admin',
      desc: 'Workspace administration and member access control'
    },
  ];

  const handleStandardLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Login failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickPersona = async (role: UserRole) => {
    setLoading(true);
    setError(null);
    try {
      await switchPersona(role);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Persona switch failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'radial-gradient(circle at 50% 20%, #1e1b4b 0%, #090d16 60%)',
      padding: 24
    }}>
      <div style={{ width: '100%', maxWidth: 960, display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 32 }}>
        {/* Left Column: Quick Personas for Hackathon Judges */}
        <div className="card" style={{ padding: 32, background: 'rgba(19, 27, 46, 0.7)', backdropFilter: 'blur(16px)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
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

          <h2 className="title-md" style={{ marginBottom: 6 }}>1-Click Persona Access (Demo Sandbox)</h2>
          <p className="text-sub" style={{ marginBottom: 20 }}>
            Select any of the 4 seeded Freshsip identities to experience role-based governance workflows:
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {personas.map((p) => (
              <button
                key={p.role}
                onClick={() => handleQuickPersona(p.role)}
                disabled={loading}
                className="card card-hoverable"
                style={{
                  padding: 14,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  textAlign: 'left',
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid var(--border-subtle)',
                  cursor: 'pointer',
                  width: '100%'
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.9rem' }}>
                    {p.name}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#818cf8', fontWeight: 600 }}>
                    {p.label}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 2 }}>
                    {p.desc}
                  </div>
                </div>
                <ArrowRight size={18} color="#818cf8" />
              </button>
            ))}
          </div>
        </div>

        {/* Right Column: Standard Email/Password Form */}
        <div className="card" style={{ padding: 32, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <h2 className="title-lg" style={{ marginBottom: 4 }}>Standard Sign In</h2>
          <p className="text-sub" style={{ marginBottom: 24 }}>
            Sign in with seeded Freshsip credentials:
          </p>

          <form onSubmit={handleStandardLogin}>
            <div className="form-group">
              <label className="form-label">Email Address</label>
              <div style={{ position: 'relative' }}>
                <input
                  type="email"
                  placeholder="creator@freshsip.demo"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input"
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Password</label>
              <input
                type="password"
                placeholder="Freshsip2026!"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                required
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 4 }}>
                Default demo password: <code>Freshsip2026!</code>
              </span>
            </div>

            {error && (
              <div style={{ padding: 10, borderRadius: 6, background: 'rgba(244,63,94,0.15)', color: '#fb7185', fontSize: '0.8rem', marginBottom: 14 }}>
                {error}
              </div>
            )}

            <button type="submit" disabled={loading} className="btn btn-primary" style={{ width: '100%', marginTop: 8, padding: '10px 16px' }}>
              {loading ? 'Authenticating...' : 'Sign In with Email'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
