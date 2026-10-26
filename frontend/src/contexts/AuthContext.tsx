import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, UserRole, AuthState } from '../types';
import { api } from '../services/api';

interface AuthContextType extends AuthState {
  login: (email: string, pass: string) => Promise<void>;
  switchPersona: (role: UserRole) => Promise<void>;
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
    isAuthenticated: false,
  });
  const [loading, setLoading] = useState(true);

  // Initialize from storage or auto-login with default persona for smooth demo testing
  useEffect(() => {
    const init = async () => {
      try {
        api.initFromStorage();
        const savedToken = localStorage.getItem('inkloom_token');
        const savedOrgId = localStorage.getItem('inkloom_org_id');

        if (savedToken) {
          const profile = await api.getMe();
          const primaryOrg = profile.organizations[0];
          setAuthState({
            token: savedToken,
            user: profile.user,
            organizationId: primaryOrg?.organization_id || savedOrgId,
            organizationName: primaryOrg?.organization_name || 'Freshsip Beverage Co.',
            organizationSlug: primaryOrg?.organization_slug || 'freshsip',
            role: primaryOrg?.role || 'content_creator',
            isAuthenticated: true,
          });
          api.setAuth(savedToken, primaryOrg?.organization_id || savedOrgId);
        } else {
          // Auto-init as Content Creator for effortless first glance
          await switchPersona('content_creator');
        }
      } catch (err) {
        console.warn('Auth initialization fallback to dev-login:', err);
        try {
          await switchPersona('content_creator');
        } catch {
          setAuthState({
            token: null,
            user: null,
            organizationId: null,
            organizationName: null,
            organizationSlug: null,
            role: null,
            isAuthenticated: false,
          });
        }
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const login = async (email: string, pass: string) => {
    setLoading(true);
    try {
      const res = await api.login(email, pass);
      api.setAuth(res.access_token, res.organization_id);
      setAuthState({
        token: res.access_token,
        user: res.user,
        organizationId: res.organization_id,
        organizationName: res.organization_name,
        organizationSlug: res.organization_slug,
        role: res.role,
        isAuthenticated: true,
      });
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
        isAuthenticated: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    api.setAuth(null, null);
    setAuthState({
      token: null,
      user: null,
      organizationId: null,
      organizationName: null,
      organizationSlug: null,
      role: null,
      isAuthenticated: false,
    });
  };

  return (
    <AuthContext.Provider value={{ ...authState, login, switchPersona, logout, loading }}>
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
