import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  BookOpen,
  FileEdit,
  CheckSquare,
  Image as ImageIcon,
  History,
  Users,
  ShieldCheck,
  Sparkles
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export const Sidebar: React.FC = () => {
  const { role, organizationName } = useAuth();

  const links = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/knowledge', label: 'Knowledge Library', icon: BookOpen },
    { to: '/content', label: 'Content Studio', icon: FileEdit },
    { to: '/approvals', label: 'Approval Queue', icon: CheckSquare },
    { to: '/image-governance', label: 'Image Governance', icon: ImageIcon },
    { to: '/audit', label: 'Audit History', icon: History },
    { to: '/team', label: 'Team & Roles', icon: Users },
  ];

  const formatRole = (r: string | null) => {
    switch (r) {
      case 'org_admin': return 'Org Admin';
      case 'knowledge_reviewer': return 'Knowledge Reviewer';
      case 'content_creator': return 'Content Creator';
      case 'approval_manager': return 'Approval Manager';
      default: return 'Member';
    }
  };

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{
          width: 38,
          height: 38,
          borderRadius: 10,
          background: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 16px rgba(99, 102, 241, 0.4)'
        }}>
          <ShieldCheck size={22} color="#fff" />
        </div>
        <div>
          <div style={{ fontWeight: 800, fontSize: '1.1rem', letterSpacing: '-0.02em', color: '#fff' }}>
            Inkloom<span style={{ color: '#6366f1' }}>.AI</span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontWeight: 600 }}>Brand Governance</div>
        </div>
      </div>

      {/* Organization Scope Pill */}
      <div style={{ margin: '14px 16px 8px 16px', padding: '10px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 10, border: '1px solid var(--border-subtle)' }}>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 700 }}>Workspace</div>
        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {organizationName || 'Freshsip Beverage Co.'}
        </div>
        <div style={{ marginTop: 4, display: 'inline-block' }}>
          <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 6, background: 'rgba(99,102,241,0.15)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.25)', fontWeight: 600 }}>
            {formatRole(role)}
          </span>
        </div>
      </div>

      {/* Nav Navigation Links */}
      <nav style={{ flex: 1, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {links.map((link) => {
          const Icon = link.icon;
          return (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 14px',
                borderRadius: '8px',
                color: isActive ? '#fff' : 'var(--text-muted)',
                backgroundColor: isActive ? 'rgba(99, 102, 241, 0.16)' : 'transparent',
                border: isActive ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid transparent',
                textDecoration: 'none',
                fontWeight: isActive ? 600 : 500,
                fontSize: '0.875rem',
                transition: 'all 0.15s ease'
              })}
            >
              <Icon size={18} />
              <span>{link.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Round 3 Improvement Banner */}
      <div style={{ padding: '14px', margin: '0 14px 16px 14px', background: 'rgba(99,102,241,0.08)', borderRadius: 10, border: '1px solid rgba(99,102,241,0.2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#a5b4fc', fontSize: '0.75rem', fontWeight: 700 }}>
          <Sparkles size={14} /> Round 3 Governance
        </div>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 4 }}>
          Deterministic evidence linking, version checksum immutability, and static-image inspection.
        </div>
      </div>
    </aside>
  );
};
