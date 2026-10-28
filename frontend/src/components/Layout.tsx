import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Navbar } from './Navbar';
import { AdminGuideModal } from './AdminGuideModal';
import { useAuth } from '../contexts/AuthContext';

export const Layout: React.FC = () => {
  const { user, role, organizationId } = useAuth();
  const [showAdminGuide, setShowAdminGuide] = useState(false);

  useEffect(() => {
    // Show only for organization administrators who have not yet dismissed it
    if (role === 'org_admin' && user?.id && organizationId) {
      const storageKey = `inkloom_admin_guide_dismissed_${user.id}_${organizationId}`;
      const dismissed = localStorage.getItem(storageKey);
      if (!dismissed) {
        setShowAdminGuide(true);
      }
    } else {
      setShowAdminGuide(false);
    }
  }, [role, user?.id, organizationId]);

  const handleDismiss = () => {
    if (user?.id && organizationId) {
      const storageKey = `inkloom_admin_guide_dismissed_${user.id}_${organizationId}`;
      localStorage.setItem(storageKey, 'true');
    }
    setShowAdminGuide(false);
  };

  return (
    <div className="app-container">
      <Sidebar />
      <div className="main-content">
        <Navbar />
        <main className="page-body">
          <Outlet />
        </main>
      </div>
      <AdminGuideModal isOpen={showAdminGuide} onClose={handleDismiss} />
    </div>
  );
};
