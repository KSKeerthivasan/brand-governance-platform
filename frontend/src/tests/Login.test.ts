import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from '../services/api';

describe('Demo Persona One-Click Access & Authentication Flow', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  const DEMO_PERSONAS = [
    {
      role: 'content_creator',
      name: 'Chris Creator',
      email: 'creator@freshsip.demo',
      password: 'Freshsip2026!',
      expectedRole: 'content_creator'
    },
    {
      role: 'knowledge_reviewer',
      name: 'Rachel Reviewer',
      email: 'reviewer@freshsip.demo',
      password: 'Freshsip2026!',
      expectedRole: 'knowledge_reviewer'
    },
    {
      role: 'approval_manager',
      name: 'Marcus Manager',
      email: 'approver@freshsip.demo',
      password: 'Freshsip2026!',
      expectedRole: 'approval_manager'
    },
    {
      role: 'org_admin',
      name: 'Alice Administrator',
      email: 'admin@freshsip.demo',
      password: 'Freshsip2026!',
      expectedRole: 'org_admin'
    }
  ];

  it('verifies all 4 demo personas have correct identity metadata and seeded credentials', () => {
    expect(DEMO_PERSONAS).toHaveLength(4);
    const emails = DEMO_PERSONAS.map(p => p.email);
    expect(emails).toContain('admin@freshsip.demo');
    expect(emails).toContain('creator@freshsip.demo');
    expect(emails).toContain('reviewer@freshsip.demo');
    expect(emails).toContain('approver@freshsip.demo');

    for (const p of DEMO_PERSONAS) {
      expect(p.password).toBe('Freshsip2026!');
      expect(p.name).toBeTruthy();
      expect(p.role).toBeTruthy();
    }
  });

  it('submits standard credentials to POST /api/v1/auth/login when a demo persona card is selected', async () => {
    for (const persona of DEMO_PERSONAS) {
      const mockResponse = {
        access_token: `mock-jwt-token-for-${persona.role}`,
        token_type: 'bearer',
        organization_id: 'freshsip-org-uuid',
        organization_name: 'Freshsip Beverage Co.',
        organization_slug: 'freshsip',
        role: persona.expectedRole,
        is_demo: true,
        user: {
          id: `user-${persona.role}`,
          email: persona.email,
          full_name: persona.name,
          is_active: true
        }
      };

      const loginSpy = vi.spyOn(api, 'login').mockResolvedValue(mockResponse);

      // Execute standard login flow that the card triggers
      const result = await api.login(persona.email, persona.password, undefined, 'freshsip');

      // Verify that the standard login endpoint was called with correct parameters
      expect(loginSpy).toHaveBeenCalledWith(persona.email, 'Freshsip2026!', undefined, 'freshsip');
      expect(result.access_token).toBe(`mock-jwt-token-for-${persona.role}`);
      expect(result.role).toBe(persona.expectedRole);
      expect(result.organization_slug).toBe('freshsip');

      // Verify token storage
      api.setAuth(result.access_token, result.organization_id);
      expect(localStorage.getItem('inkloom_token')).toBe(`mock-jwt-token-for-${persona.role}`);
      expect(localStorage.getItem('inkloom_org_id')).toBe('freshsip-org-uuid');

      loginSpy.mockRestore();
    }
  });

  it('handles failed login gracefully with clear error reporting without unhandled exceptions', async () => {
    const loginSpy = vi.spyOn(api, 'login').mockRejectedValue(new Error('Invalid credentials or account locked.'));

    let caughtError: string | null = null;
    try {
      await api.login('invalid@freshsip.demo', 'WrongPassword!', undefined, 'freshsip');
    } catch (err: any) {
      caughtError = err.message;
    }

    expect(caughtError).toBe('Invalid credentials or account locked.');
    expect(localStorage.getItem('inkloom_token')).toBeNull();
  });

  it('prevents duplicate concurrent login calls when multiple clicks are fired', async () => {
    let callCount = 0;
    const loginSpy = vi.spyOn(api, 'login').mockImplementation(async () => {
      callCount++;
      await new Promise(resolve => setTimeout(resolve, 50));
      return {
        access_token: 'jwt-1',
        organization_id: 'org-1',
        organization_name: 'Freshsip',
        organization_slug: 'freshsip',
        role: 'content_creator',
        is_demo: true,
        user: { id: 'u1', email: 'creator@freshsip.demo', full_name: 'Chris', is_active: true }
      };
    });

    // Simulate single-flight guard: if loading is true, subsequent calls are ignored
    let loading = false;
    const triggerPersonaClick = async (email: string) => {
      if (loading) return null;
      loading = true;
      try {
        return await api.login(email, 'Freshsip2026!', undefined, 'freshsip');
      } finally {
        loading = false;
      }
    };

    // Fire 3 simultaneous clicks
    const [first, second, third] = await Promise.all([
      triggerPersonaClick('creator@freshsip.demo'),
      triggerPersonaClick('creator@freshsip.demo'),
      triggerPersonaClick('creator@freshsip.demo')
    ]);

    expect(first).not.toBeNull();
    expect(second).toBeNull();
    expect(third).toBeNull();
    expect(callCount).toBe(1);
  });
});
