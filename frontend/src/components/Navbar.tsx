import React, { useState } from 'react';
import { User, LogOut, ChevronDown, Check, Shield, UserCheck } from 'lucide-react';
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
      {/* Platform Title & Demo Note */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <span style={{ fontSize: '0.8125rem', color: 'var(--text-dim)', fontWeight: 600 }}>
          Deterministic Pre-Publication Governance
        </span>
        <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.1)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.25)', fontWeight: 600 }}>
          Live API Active
        </span>
      </div>

      {/* Right Controls: Persona Switcher & Profile */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', position: 'relative' }}>
        {/* Normal Login: Display Authenticated User & Actual Role (No Switcher) */}
        {!isDemo && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 12px',
              fontSize: '0.8125rem',
              background: 'rgba(255, 255, 255, 0.05)',
              borderRadius: 6,
              border: '1px solid rgba(255, 255, 255, 0.1)',
            }}
          >
            <Shield size={15} color="#818cf8" />
            <span style={{ color: 'var(--text-dim)' }}>User:</span>
            <strong style={{ color: '#fff' }}>{user?.full_name || 'Authenticated User'}</strong>
            <span
              style={{
                marginLeft: 4,
                fontSize: '0.7rem',
                fontWeight: 600,
                padding: '2px 8px',
                borderRadius: 4,
                background: 'rgba(99, 102, 241, 0.2)',
                color: '#a5b4fc',
                border: '1px solid rgba(99, 102, 241, 0.35)',
              }}
            >
              {formatRole(role)}
            </span>
          </div>
        )}

        {/* Demo Mode Only: Fast Persona Switcher Dropdown */}
        {isDemo && (
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="btn btn-secondary"
              style={{ padding: '6px 12px', fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: 8 }}
              title="Switch Persona to test different RBAC permissions"
            >
              <UserCheck size={16} color="#818cf8" />
              <span>Persona: <strong style={{ color: '#fff' }}>{user?.full_name || 'Switch Role'}</strong></span>
              <ChevronDown size={14} color="var(--text-dim)" />
            </button>

            {dropdownOpen && (
              <div style={{
                position: 'absolute',
                right: 0,
                top: '115%',
                width: 320,
                background: '#131b2e',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                borderRadius: 12,
                padding: 8,
                boxShadow: '0 12px 36px rgba(0,0,0,0.5)',
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
                        background: isSelected ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                        border: isSelected ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid transparent',
                        color: 'var(--text-main)',
                        cursor: 'pointer',
                        textAlign: 'left',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <div style={{ marginTop: 2 }}>
                        {isSelected ? <Check size={16} color="#818cf8" /> : <div style={{ width: 16 }} />}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: '0.85rem', color: isSelected ? '#fff' : 'var(--text-main)' }}>
                          {p.name}
                        </div>
                        <div style={{ fontSize: '0.72rem', color: '#818cf8', fontWeight: 600 }}>
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

        {/* User Profile Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 10px', background: 'rgba(255,255,255,0.04)', borderRadius: 20, border: '1px solid var(--border-subtle)' }}>
          <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#312e81', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#c7d2fe', fontWeight: 700, fontSize: '0.75rem' }}>
            {user?.full_name?.charAt(0) || 'U'}
          </div>
          <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-main)' }}>
            {user?.email}
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
