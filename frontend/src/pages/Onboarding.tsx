import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  ShieldCheck,
  Building2,
  Sparkles,
  ArrowRight,
  User,
  Mail,
  Lock,
  Tag,
  FileText,
  AlertCircle,
  CheckCircle2
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export const Onboarding: React.FC = () => {
  const { onboard } = useAuth();
  const navigate = useNavigate();

  // Form Fields
  const [orgName, setOrgName] = useState('');
  const [orgSlug, setOrgSlug] = useState('');
  const [slugManuallyEdited, setSlugManuallyEdited] = useState(false);
  const [brandName, setBrandName] = useState('');
  const [brandDesc, setBrandDesc] = useState('');
  const [adminName, setAdminName] = useState('');
  const [adminEmail, setAdminEmail] = useState('');
  const [adminPassword, setAdminPassword] = useState('');

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auto-generate slug from organization name if not manually edited
  const handleOrgNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setOrgName(val);
    if (!slugManuallyEdited) {
      const generated = val
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
      setOrgSlug(generated);
    }
    if (!brandName) {
      setBrandName(val);
    }
  };

  const handleSlugChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSlugManuallyEdited(true);
    setOrgSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (adminPassword.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    if (!orgSlug.trim()) {
      setError('Organization slug is required.');
      return;
    }

    setLoading(true);
    try {
      await onboard({
        organization_name: orgName.trim(),
        organization_slug: orgSlug.trim(),
        brand_name: brandName.trim() || orgName.trim(),
        brand_description: brandDesc.trim() || undefined,
        admin_full_name: adminName.trim(),
        admin_email: adminEmail.trim(),
        admin_password: adminPassword
      });

      // Navigate directly into the newly created organization workspace
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Failed to create organization. Please verify your details.');
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
      background: 'radial-gradient(circle at 50% 15%, #1e1b4b 0%, #090d16 70%)',
      padding: '40px 20px'
    }}>
      <div style={{ width: '100%', maxWidth: 860 }}>
        {/* Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 12,
            marginBottom: 12
          }}>
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
            <span style={{ fontSize: '1.6rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
              Inkloom<span style={{ color: '#6366f1' }}>.AI</span>
            </span>
          </div>
          <h1 className="title-xl" style={{ fontSize: '1.75rem' }}>
            Onboard Your Organization
          </h1>
          <p className="text-sub" style={{ maxWidth: 540, margin: '8px auto 0 auto' }}>
            Set up an isolated enterprise workspace with brand-governance policies, verified truth libraries, and immutable review workflows.
          </p>
        </div>

        {/* Onboarding Card */}
        <div className="card" style={{
          padding: 36,
          background: 'rgba(19, 27, 46, 0.75)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          boxShadow: '0 20px 48px rgba(0, 0, 0, 0.45)'
        }}>
          {error && (
            <div style={{
              padding: '12px 16px',
              borderRadius: 8,
              background: 'rgba(244, 63, 94, 0.12)',
              border: '1px solid rgba(244, 63, 94, 0.3)',
              color: '#fb7185',
              fontSize: '0.85rem',
              marginBottom: 24,
              display: 'flex',
              alignItems: 'center',
              gap: 10
            }}>
              <AlertCircle size={18} style={{ flexShrink: 0 }} />
              <div>{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {/* Step 1: Workspace & Tenant Details */}
            <div style={{ marginBottom: 28 }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: '0.85rem',
                fontWeight: 700,
                color: '#a5b4fc',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: 14
              }}>
                <Building2 size={16} /> 1. Organization & Tenant Setup
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label">Company / Organization Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Veritas Botanical Tea Co."
                    value={orgName}
                    onChange={handleOrgNameChange}
                    className="input"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">
                    Organization Slug * <span style={{ color: 'var(--text-dim)', fontSize: '0.72rem' }}>(Unique Workspace ID)</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. veritas-tea"
                    value={orgSlug}
                    onChange={handleSlugChange}
                    className="input"
                    style={{ fontFamily: 'monospace' }}
                  />
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: 4 }}>
                    Tenant URL key: <code>/{orgSlug || 'my-org'}</code>
                  </span>
                </div>
              </div>
            </div>

            {/* Step 2: Initial Brand Profile */}
            <div style={{ marginBottom: 28, paddingTop: 20, borderTop: '1px solid var(--border-subtle)' }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: '0.85rem',
                fontWeight: 700,
                color: '#a5b4fc',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: 14
              }}>
                <Tag size={16} /> 2. Initial Brand Profile
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label">Primary Brand Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Veritas Botanical"
                    value={brandName}
                    onChange={(e) => setBrandName(e.target.value)}
                    className="input"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Brand Positioning / Description</label>
                  <input
                    type="text"
                    placeholder="e.g. Organic loose-leaf herbal wellness infusions"
                    value={brandDesc}
                    onChange={(e) => setBrandDesc(e.target.value)}
                    className="input"
                  />
                </div>
              </div>
            </div>

            {/* Step 3: Administrator Credentials */}
            <div style={{ marginBottom: 32, paddingTop: 20, borderTop: '1px solid var(--border-subtle)' }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: '0.85rem',
                fontWeight: 700,
                color: '#a5b4fc',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: 14
              }}>
                <User size={16} /> 3. Primary Organization Administrator
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label">Admin Full Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Victor Veritas"
                    value={adminName}
                    onChange={(e) => setAdminName(e.target.value)}
                    className="input"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Admin Work Email *</label>
                  <input
                    type="email"
                    required
                    placeholder="admin@veritastea.com"
                    value={adminEmail}
                    onChange={(e) => setAdminEmail(e.target.value)}
                    className="input"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Admin Password * (Min 8 chars)</label>
                  <input
                    type="password"
                    required
                    placeholder="••••••••••••"
                    value={adminPassword}
                    onChange={(e) => setAdminPassword(e.target.value)}
                    className="input"
                    minLength={8}
                  />
                </div>
              </div>
            </div>

            {/* Submit Action */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: 16,
              borderTop: '1px solid var(--border-subtle)'
            }}>
              <Link
                to="/login"
                style={{
                  color: 'var(--text-muted)',
                  fontSize: '0.85rem',
                  textDecoration: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6
                }}
              >
                ← Back to Login
              </Link>

              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary"
                style={{
                  padding: '12px 28px',
                  fontSize: '0.95rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8
                }}
              >
                {loading ? 'Creating Workspace...' : (
                  <>
                    <Sparkles size={18} /> Launch Organization Workspace
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
