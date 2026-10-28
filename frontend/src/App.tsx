import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { KnowledgeLibrary } from './pages/KnowledgeLibrary';
import { ContentStudio } from './pages/ContentStudio';
import { ApprovalQueue } from './pages/ApprovalQueue';
import { ImageGovernance } from './pages/ImageGovernance';
import { AuditHistory } from './pages/AuditHistory';
import { TeamManagement } from './pages/TeamManagement';
import { Login } from './pages/Login';
import { Onboarding } from './pages/Onboarding';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  if (loading) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#090d16', color: '#818cf8', fontWeight: 600 }}>
        Loading Inkloom AI Workspace...
      </div>
    );
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="knowledge" element={<KnowledgeLibrary />} />
            <Route path="brand-assets" element={<Navigate to="/knowledge?tab=assets" replace />} />
            <Route path="content" element={<ContentStudio />} />
            <Route path="approvals" element={<ApprovalQueue />} />
            <Route path="image-governance" element={<ImageGovernance />} />
            <Route path="audit" element={<AuditHistory />} />
            <Route path="team" element={<TeamManagement />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
