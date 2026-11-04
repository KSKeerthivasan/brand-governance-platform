import React, { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  BookOpen,
  FileEdit,
  CheckSquare,
  History,
  Users,
  Sparkles,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export const Sidebar: React.FC = () => {
  const { role, organizationName } = useAuth();
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    return localStorage.getItem('inkloom_sidebar_collapsed') === 'true';
  });

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem('inkloom_sidebar_collapsed', String(next));
  };

  const links = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard, id: 'sidebar-nav-dashboard' },
    { to: '/knowledge', label: 'Knowledge Library', icon: BookOpen, id: 'sidebar-nav-knowledge' },
    { to: '/content', label: 'Content Studio', icon: FileEdit, id: 'sidebar-nav-content' },
    { to: '/approvals', label: 'Approval Queue', icon: CheckSquare, id: 'sidebar-nav-approvals' },
    { to: '/audit', label: 'Audit History', icon: History, id: 'sidebar-nav-audit' },
    { to: '/team', label: 'Team & Roles', icon: Users, id: 'sidebar-nav-team' },
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
    <aside
      className="sidebar"
      style={{
        width: collapsed ? 76 : 220,
        background: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: collapsed ? 'center' : 'stretch',
        padding: collapsed ? '16px 8px' : '16px 12px',
        transition: 'width 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
        position: 'relative',
        zIndex: 10
      }}
    >
      {/* Workspace pill when expanded */}
      {!collapsed && (
        <div style={{
          margin: '0 4px 14px 4px',
          padding: '8px 12px',
          background: 'rgba(255,255,255,0.025)',
          borderRadius: 10,
          border: '1px solid var(--border-subtle)'
        }}>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 700 }}>
            Workspace
          </div>
          <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-main)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {organizationName || 'Freshsip Beverage Co.'}
          </div>
          <div style={{ marginTop: 3 }}>
            <span style={{ fontSize: '0.68rem', padding: '1px 6px', borderRadius: 4, background: 'rgba(74,222,128,0.12)', color: '#4ade80', border: '1px solid rgba(74,222,128,0.25)', fontWeight: 600 }}>
              {formatRole(role)}
            </span>
          </div>
        </div>
      )}

      {/* Nav Navigation Links */}
      <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px', alignItems: collapsed ? 'center' : 'stretch' }}>
        {links.map((link) => {
          const Icon = link.icon;
          return (
            <NavLink
              key={link.to}
              id={link.id}
              to={link.to}
              end={link.to === '/'}
              title={link.label}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: collapsed ? 0 : '12px',
                justifyContent: collapsed ? 'center' : 'flex-start',
                padding: collapsed ? '4px' : '6px 10px',
                borderRadius: '12px',
                textDecoration: 'none',
                transition: 'all 0.15s ease',
              })}
            >
              {({ isActive }) => (
                <>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 12,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: isActive ? '#22c55e' : 'rgba(255, 255, 255, 0.035)',
                      color: isActive ? '#052e16' : '#94a3b8',
                      border: isActive ? 'none' : '1px solid rgba(255, 255, 255, 0.06)',
                      boxShadow: isActive ? '0 0 16px rgba(34, 197, 94, 0.35)' : 'none',
                      transition: 'all 0.15s ease',
                      flexShrink: 0
                    }}
                  >
                    <Icon size={20} strokeWidth={isActive ? 2.2 : 1.8} />
                  </div>
                  {!collapsed && (
                    <span style={{
                      fontSize: '0.84rem',
                      fontWeight: isActive ? 700 : 500,
                      color: isActive ? '#fff' : 'var(--text-muted)',
                      whiteSpace: 'nowrap'
                    }}>
                      {link.label}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Round 3 Improvement Banner */}
      <div style={{
        padding: collapsed ? '8px 6px' : '10px 12px',
        margin: '12px 0 6px 0',
        background: 'rgba(255, 255, 255, 0.025)',
        borderRadius: 12,
        border: '1px solid var(--border-subtle)',
        width: collapsed ? 60 : 'auto',
        textAlign: collapsed ? 'center' : 'left'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: collapsed ? 'center' : 'flex-start', gap: 6, color: '#4ade80', fontSize: '0.72rem', fontWeight: 700 }}>
          <Sparkles size={13} color="#4ade80" />
          {!collapsed && <span>Round 3 Governance</span>}
        </div>
        <div style={{ fontSize: '0.67rem', color: 'var(--text-dim)', marginTop: 4, lineHeight: 1.35, display: collapsed ? 'none' : 'block' }}>
          Deterministic evidence linking, version checksum immutability, and static-image inspection.
        </div>
      </div>

      {/* Collapse / Expand Toggle Button */}
      <button
        onClick={toggleCollapsed}
        style={{
          marginTop: 6,
          background: 'none',
          border: 'none',
          color: 'var(--text-dim)',
          cursor: 'pointer',
          padding: '6px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '100%',
          borderRadius: 8,
          transition: 'color 0.15s ease'
        }}
        title={collapsed ? "Expand navigation sidebar" : "Collapse navigation sidebar"}
        aria-label={collapsed ? "Expand navigation sidebar" : "Collapse navigation sidebar"}
      >
        {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
    </aside>
  );
};
