import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, UserRole, AuthState } from '../types';
import { api } from '../services/api';

interface AuthContextType extends AuthState {
  login: (email: string, pass: string, orgId?: string, orgSlug?: string) => Promise<void>;
  switchOrg: (orgId?: string, orgSlug?: string) => Promise<void>;
  switchPersona: (role: UserRole) => Promise<void>;
  onboard: (payload: {
    organization_name: string;
    organization_slug: string;
    brand_name: string;
    brand_description?: string;
    admin_full_name: string;
    admin_email: string;
    admin_password: string;
  }) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>({
    token: null,
    user: null,
    organizationId: null,
    organizationName: null,
    organizationSlug: null,
    role: null,
    isDemo: false,
    isAuthenticated: false,
  });
  const [loading, setLoading] = useState(true);

  // Initialize from storage
  useEffect(() => {
    const init = async () => {
      try {
        api.initFromStorage();
        const savedToken = localStorage.getItem('inkloom_token');
        const savedOrgId = localStorage.getItem('inkloom_org_id');

        if (savedToken) {
          const profile = await api.getMe();
          const targetOrg = profile.organizations?.find((o: any) => o.organization_id === savedOrgId) || profile.organizations?.[0];
          setAuthState({
            token: savedToken,
            user: profile.user,
            organizationId: targetOrg?.organization_id || savedOrgId,
            organizationName: targetOrg?.organization_name || 'Freshsip Beverage Co.',
            organizationSlug: targetOrg?.organization_slug || 'freshsip',
            role: targetOrg?.role || 'content_creator',
            isDemo: Boolean(profile.is_demo),
            isAuthenticated: true,
          });
          api.setAuth(savedToken, targetOrg?.organization_id || savedOrgId);
        } else {
          setAuthState({
            token: null,
            user: null,
            organizationId: null,
            organizationName: null,
            organizationSlug: null,
            role: null,
            isDemo: false,
            isAuthenticated: false,
          });
        }
      } catch (err) {
        console.warn('Auth initialization error:', err);
        setAuthState({
          token: null,
          user: null,
          organizationId: null,
          organizationName: null,
          organizationSlug: null,
          role: null,
          isDemo: false,
          isAuthenticated: false,
        });
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const login = async (email: string, pass: string, orgId?: string, orgSlug?: string) => {
    setLoading(true);
    try {
      const res = await api.login(email, pass, orgId, orgSlug);
      api.setAuth(res.access_token, res.organization_id);
      setAuthState({
        token: res.access_token,
        user: res.user,
        organizationId: res.organization_id,
        organizationName: res.organization_name,
        organizationSlug: res.organization_slug,
        role: res.role,
        isDemo: Boolean(res.is_demo),
        isAuthenticated: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const switchOrg = async (orgId?: string, orgSlug?: string) => {
    setLoading(true);
    try {
      const res = await api.switchOrg(orgId, orgSlug);
      api.setAuth(res.access_token, res.organization_id);
      setAuthState(prev => ({
        ...prev,
        token: res.access_token,
        user: res.user,
        organizationId: res.organization_id,
        organizationName: res.organization_name,
        organizationSlug: res.organization_slug,
        role: res.role,
        isDemo: res.is_demo !== undefined ? Boolean(res.is_demo) : prev.isDemo,
        isAuthenticated: true,
      }));
    } finally {
      setLoading(false);
    }
  };

  const switchPersona = async (role: UserRole) => {
    setLoading(true);
    try {
      const res = await api.devLogin(role, 'freshsip');
      api.setAuth(res.access_token, res.organization_id);
      setAuthState({
        token: res.access_token,
        user: res.user,
        organizationId: res.organization_id,
        organizationName: res.organization_name,
        organizationSlug: res.organization_slug,
        role: res.role,
        isDemo: true,
        isAuthenticated: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const onboard = async (payload: {
    organization_name: string;
    organization_slug: string;
    brand_name: string;
    brand_description?: string;
    admin_full_name: string;
    admin_email: string;
    admin_password: string;
  }) => {
    setLoading(true);
    try {
      const res = await api.onboardOrganization(payload);
      api.setAuth(res.access_token, res.organization_id);
      setAuthState({
        token: res.access_token,
        user: res.user,
        organizationId: res.organization_id,
        organizationName: res.organization_name,
        organizationSlug: res.organization_slug,
        role: res.role,
        isDemo: Boolean(res.is_demo),
        isAuthenticated: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {}
    setAuthState({
      token: null,
      user: null,
      organizationId: null,
      organizationName: null,
      organizationSlug: null,
      role: null,
      isDemo: false,
      isAuthenticated: false,
    });
  };

  return (
    <AuthContext.Provider value={{ ...authState, login, switchOrg, switchPersona, onboard, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
