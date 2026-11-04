import React, { useState } from 'react';
import { User, LogOut, ChevronDown, Check, Shield, UserCheck, ShieldCheck } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { UserRole } from '../types';

export const Navbar: React.FC = () => {
  const { user, role, isDemo, switchPersona, logout } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const formatRole = (r?: UserRole | string | null) => {
    switch (r) {
      case 'org_admin':
        return 'Org Admin';
      case 'knowledge_reviewer':
        return 'Knowledge Reviewer';
      case 'content_creator':
        return 'Content Creator';
      case 'approval_manager':
        return 'Approval Manager';
      default:
        return r || 'Member';
    }
  };

  const personas: { role: UserRole; name: string; email: string; label: string; desc: string }[] = [
    {
      role: 'content_creator',
      name: 'Chris Creator',
      email: 'creator@freshsip.demo',
      label: 'Content Creator',
      desc: 'Creates drafts, runs checks, submits versions'
    },
    {
      role: 'knowledge_reviewer',
      name: 'Rachel Reviewer',
      email: 'reviewer@freshsip.demo',
      label: 'Knowledge Reviewer',
      desc: 'Uploads guidelines, reviews candidate facts & rules'
    },
    {
      role: 'approval_manager',
      name: 'Marcus Manager',
      email: 'approver@freshsip.demo',
      label: 'Approval Manager',
      desc: 'Reviews queue, issues official publication approvals'
    },
    {
      role: 'org_admin',
      name: 'Alice Administrator',
      email: 'admin@freshsip.demo',
      label: 'Org Admin',
      desc: 'Workspace settings, audit log, role assignment'
    },
  ];

  const handleSelectPersona = async (pRole: UserRole) => {
    setDropdownOpen(false);
    await switchPersona(pRole);
  };

  return (
    <header className="top-navbar">
      {/* Brand Logo & Platform Scope */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {/* Brand Logo Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: 34,
            height: 34,
            borderRadius: 8,
            background: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 12px rgba(99, 102, 241, 0.35)'
          }}>
            <ShieldCheck size={20} color="#fff" />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '1.05rem', letterSpacing: '-0.02em', color: '#fff', lineHeight: 1.15 }}>
              Inkloom<span style={{ color: '#a5b4fc' }}>.Ai</span>
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 600 }}>Brand Governance</div>
          </div>
        </div>

        {/* Vertical Divider */}
        <div style={{ height: 26, width: 1, background: 'var(--border-subtle)' }} />

        {/* Platform Eyebrow & Status */}
        <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontWeight: 500 }}>
          Deterministic Pre-Publication Governance
        </span>
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          fontSize: '0.72rem',
          padding: '3px 10px',
          borderRadius: 20,
          background: 'rgba(34, 197, 94, 0.12)',
          color: '#4ade80',
          border: '1px solid rgba(34, 197, 94, 0.28)',
          fontWeight: 600
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
          Live API Active
        </div>
      </div>

      {/* Right Controls: User Pill & Profile & Persona Switcher */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', position: 'relative' }}>
        {/* User Pill with Role Badge */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '5px 12px',
            fontSize: '0.8125rem',
            background: 'rgba(255, 255, 255, 0.035)',
            borderRadius: 20,
            border: '1px solid var(--border-subtle)',
          }}
        >
          <Shield size={14} color="#a5b4fc" />
          <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>User:</span>
          <strong style={{ color: '#fff', fontSize: '0.8125rem' }}>{user?.full_name || 'Alice Administrator'}</strong>
          <span
            style={{
              marginLeft: 4,
              fontSize: '0.7rem',
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: 12,
              background: '#2e1d4d',
              color: '#d8b4fe',
              border: '1px solid #581c87',
            }}
          >
            {formatRole(role)}
          </span>
        </div>

        {/* Demo Mode Fast Persona Switcher Dropdown */}
        {isDemo && (
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="btn btn-secondary"
              style={{ padding: '6px 12px', fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: 6, borderRadius: 20 }}
              title="Switch Persona to test different RBAC permissions"
            >
              <UserCheck size={14} color="#4ade80" />
              <span>Persona</span>
              <ChevronDown size={14} color="var(--text-dim)" />
            </button>

            {dropdownOpen && (
              <div style={{
                position: 'absolute',
                right: 0,
                top: '125%',
                width: 320,
                background: '#131915',
                border: '1px solid var(--border-medium)',
                borderRadius: 14,
                padding: 8,
                boxShadow: '0 16px 40px rgba(0,0,0,0.6)',
                zIndex: 100,
                display: 'flex',
                flexDirection: 'column',
                gap: 4
              }}>
                <div style={{ padding: '8px 10px', fontSize: '0.72rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Fast Persona Switcher (RBAC Demo)
                </div>
                {personas.map((p) => {
                  const isSelected = role === p.role;
                  return (
                    <button
                      key={p.role}
                      onClick={() => handleSelectPersona(p.role)}
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 10,
                        padding: '10px',
                        borderRadius: 8,
                        background: isSelected ? 'rgba(74, 222, 128, 0.12)' : 'transparent',
                        border: isSelected ? '1px solid rgba(74, 222, 128, 0.3)' : '1px solid transparent',
                        color: 'var(--text-main)',
                        cursor: 'pointer',
                        textAlign: 'left',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <div style={{ marginTop: 2 }}>
                        {isSelected ? <Check size={16} color="#4ade80" /> : <div style={{ width: 16 }} />}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: '0.85rem', color: isSelected ? '#fff' : 'var(--text-main)' }}>
                          {p.name}
                        </div>
                        <div style={{ fontSize: '0.72rem', color: '#4ade80', fontWeight: 600 }}>
                          {p.label}
                        </div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: 2 }}>
                          {p.desc}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* User Profile Pill with Avatar & Logout */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 10px', background: 'rgba(255,255,255,0.035)', borderRadius: 20, border: '1px solid var(--border-subtle)' }}>
          <div style={{ width: 26, height: 26, borderRadius: '50%', background: '#6b21a8', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ffffff', fontWeight: 700, fontSize: '0.75rem' }}>
            {user?.full_name?.charAt(0) || user?.email?.charAt(0).toUpperCase() || 'A'}
          </div>
          <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-main)' }}>
            {user?.email || 'admin@freshsip.demo'}
          </span>
          <button
            onClick={logout}
            style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center' }}
            title="Log out"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </header>
  );
};
