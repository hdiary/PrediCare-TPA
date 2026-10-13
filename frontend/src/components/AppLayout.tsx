import { useState, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import type { Role } from '@/lib/types';

const ROLE_PREFIX: Record<Role, string> = {
  insured: '/assurant',
  provider: '/professionnel',
  manager: '/gestionnaire',
  admin: '/admin',
};

export function AppLayout({ allowedRoles, children }: { allowedRoles: Role[]; children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-surface-200 border-t-primary-600 rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    return <Navigate to="/acces-refuse" replace />;
  }

  const expectedPrefix = ROLE_PREFIX[user.role];
  if (!location.pathname.startsWith(expectedPrefix)) {
    return <Navigate to={expectedPrefix} replace />;
  }

  return (
    <div className="min-h-screen flex">
      <Sidebar collapsed={collapsed} onToggleCollapse={() => setCollapsed(!collapsed)} />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar onToggleMobileSidebar={() => setMobileSidebarOpen(!mobileSidebarOpen)} />
        <main className="flex-1 p-4 md:p-6 lg:p-8 pb-20 md:pb-6 max-w-[1400px] w-full mx-auto">
          {children}
        </main>
        <footer className="px-6 py-3 border-t border-surface-300/80 dark:border-surface-700 text-xs text-surface-400 flex items-center justify-between flex-wrap gap-2">
          <span>Données synthétiques - Démonstration</span>
          <div className="flex gap-4">
            <span className="hover:text-surface-600 cursor-pointer">Confidentialité</span>
            <span className="hover:text-surface-600 cursor-pointer">Mentions IA</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
