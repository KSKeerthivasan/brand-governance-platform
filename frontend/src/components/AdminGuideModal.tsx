import React from 'react';
import {
  Users,
  BookOpen,
  LayoutDashboard,
  History,
  ShieldCheck,
  ArrowRight,
  Check
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface AdminGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AdminGuideModal: React.FC<AdminGuideModalProps> = ({ isOpen, onClose }) => {
  const navigate = useNavigate();

  if (!isOpen) return null;

  const handleNavigate = (path: string) => {
    onClose();
    navigate(path);
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(5, 8, 16, 0.75)',
      backdropFilter: 'blur(10px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '20px'
    }}>
      <div style={{
        background: '#131b2e',
        border: '1px solid rgba(99, 102, 241, 0.35)',
        boxShadow: '0 20px 50px rgba(0, 0, 0, 0.6), 0 0 30px rgba(99, 102, 241, 0.2)',
        borderRadius: 16,
        width: '100%',
        maxWidth: 720,
        overflow: 'hidden',
        animation: 'fadeIn 0.2s ease-out'
      }}>
        {/* Header */}
        <div style={{
          padding: '24px 28px',
          borderBottom: '1px solid var(--border-subtle)',
          background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.6) 0%, rgba(19, 27, 46, 0.9) 100%)',
          display: 'flex',
          alignItems: 'center',
          gap: 14
        }}>
          <div style={{
            width: 44,
            height: 44,
            borderRadius: 12,
            background: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 16px rgba(99, 102, 241, 0.4)',
            flexShrink: 0
          }}>
            <ShieldCheck size={24} color="#fff" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em', marginBottom: 4 }}>
              Welcome to Inkloom AI
            </h2>
            <p style={{ fontSize: '0.86rem', color: '#cbd5e1' }}>
              Here is a quick guide to your responsibilities as an organization administrator.
            </p>
          </div>
        </div>

        {/* 4 Core Responsibilities with Visual Pointers to Sidebar */}
        <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 14, maxHeight: '65vh', overflowY: 'auto' }}>
          
          {/* Item A: Team & Roles */}
          <div style={{
            padding: '16px',
            borderRadius: 12,
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 16
          }}>
            <div style={{ display: 'flex', gap: 14 }}>
              <div style={{
                width: 36,
                height: 36,
                borderRadius: 8,
                background: 'rgba(99, 102, 241, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <Users size={18} color="#818cf8" />
              </div>
              <div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
                  Team & Roles
                  <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 4, background: 'rgba(99, 102, 241, 0.2)', color: '#a5b4fc', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
                    Sidebar &rarr; Team & Roles
                  </span>
                </div>
                <p style={{ fontSize: '0.83rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                  Add team members and assign the appropriate roles so each person can perform their responsibilities.
                </p>
              </div>
            </div>
            <button
              onClick={() => handleNavigate('/team')}
              className="btn btn-secondary btn-sm"
              style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.76rem', padding: '6px 10px' }}
            >
              Open <ArrowRight size={12} />
            </button>
          </div>

          {/* Item B: Knowledge Library */}
          <div style={{
            padding: '16px',
            borderRadius: 12,
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 16
          }}>
            <div style={{ display: 'flex', gap: 14 }}>
              <div style={{
                width: 36,
                height: 36,
                borderRadius: 8,
                background: 'rgba(6, 182, 212, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <BookOpen size={18} color="#22d3ee" />
              </div>
              <div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
                  Knowledge Library
                  <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 4, background: 'rgba(6, 182, 212, 0.2)', color: '#67e8f9', border: '1px solid rgba(6, 182, 212, 0.3)' }}>
                    Sidebar &rarr; Knowledge Library
                  </span>
                </div>
                <p style={{ fontSize: '0.83rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                  Onboard your brand knowledge here. Minimum requirements: <strong>1. Brand guidelines PDF (Required)</strong> and <strong>2. Official brand logo (Required)</strong>. Product facts, claims, and reference creatives are optional and only requested when needed for specific checks.
                </p>
              </div>
            </div>
            <button
              onClick={() => handleNavigate('/knowledge')}
              className="btn btn-secondary btn-sm"
              style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.76rem', padding: '6px 10px' }}
            >
              Open <ArrowRight size={12} />
            </button>
          </div>

          {/* Item C: Dashboard */}
          <div style={{
            padding: '16px',
            borderRadius: 12,
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 16
          }}>
            <div style={{ display: 'flex', gap: 14 }}>
              <div style={{
                width: 36,
                height: 36,
                borderRadius: 8,
                background: 'rgba(16, 185, 129, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <LayoutDashboard size={18} color="#34d399" />
              </div>
              <div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
                  Dashboard
                  <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.2)', color: '#6ee7b7', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                    Sidebar &rarr; Dashboard
                  </span>
                </div>
                <p style={{ fontSize: '0.83rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                  Monitor organization activity, governance progress, and available performance metrics from your Dashboard.
                </p>
              </div>
            </div>
            <button
              onClick={() => handleNavigate('/')}
              className="btn btn-secondary btn-sm"
              style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.76rem', padding: '6px 10px' }}
            >
              Open <ArrowRight size={12} />
            </button>
          </div>

          {/* Item D: Audit History */}
          <div style={{
            padding: '16px',
            borderRadius: 12,
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 16
          }}>
            <div style={{ display: 'flex', gap: 14 }}>
              <div style={{
                width: 36,
                height: 36,
                borderRadius: 8,
                background: 'rgba(245, 158, 11, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <History size={18} color="#fbbf24" />
              </div>
              <div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
                  Audit History
                  <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 4, background: 'rgba(245, 158, 11, 0.2)', color: '#fcd34d', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                    Sidebar &rarr; Audit History
                  </span>
                </div>
                <p style={{ fontSize: '0.83rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                  Review the recorded history of actions performed within your organization for traceability and accountability.
                </p>
              </div>
            </div>
            <button
              onClick={() => handleNavigate('/audit')}
              className="btn btn-secondary btn-sm"
              style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.76rem', padding: '6px 10px' }}
            >
              Open <ArrowRight size={12} />
            </button>
          </div>

        </div>

        {/* Footer with Clear "Got it" Button */}
        <div style={{
          padding: '18px 28px',
          borderTop: '1px solid var(--border-subtle)',
          background: 'rgba(11, 17, 30, 0.7)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
            This instructional guide will not be shown again.
          </div>
          <button
            onClick={onClose}
            className="btn btn-primary"
            style={{
              padding: '10px 24px',
              fontSize: '0.9rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              boxShadow: '0 0 20px rgba(99, 102, 241, 0.4)'
            }}
          >
            <Check size={16} /> Got it
          </button>
        </div>
      </div>
    </div>
  );
};
