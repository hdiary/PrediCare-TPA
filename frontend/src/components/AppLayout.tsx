import { Suspense, useState, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { PageLoader } from './PageLoader';
import { mockedFeatureList, type Feature } from '@/lib/api';

const FEATURE_LABELS: Record<Feature, string> = {
  auth: 'connexion', alerts: 'alertes', invoices: 'factures', settings: 'configuration', audit: "journal d'audit",
  users: 'utilisateurs', health: 'état des services',
  models: 'versions du modèle',
  prescriptions: 'ordonnances et alertes de prescription', password: 'mot de passe oublié',
};
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
    return <PageLoader fullscreen />;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (user.must_change_password) {
    return <Navigate to="/premiere-connexion" replace />;
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
        {mockedFeatureList().length > 0 && (
          <div role="status" className="px-4 md:px-8 py-2 text-xs bg-warning-50 text-warning-700 dark:bg-warning-900/30 dark:text-warning-300 border-b border-warning-200 dark:border-warning-800">
            Données de démonstration (non réelles) : {mockedFeatureList().map((f) => FEATURE_LABELS[f]).join(', ')}.
          </div>
        )}
        <main className="flex-1 p-4 md:p-6 lg:p-8 pb-6 max-w-[1400px] w-full mx-auto">
          <Suspense fallback={<PageLoader />}>
            <div key={location.pathname} className="animate-page-in motion-reduce:animate-none">
              {children}
            </div>
          </Suspense>
        </main>
        <footer className="px-4 md:px-8 pt-4 pb-20 md:pb-4 border-t border-surface-300/80 dark:border-surface-700 text-xs text-surface-400 flex items-center justify-between flex-wrap gap-2">
          <div className="flex gap-4">
            <span className="hover:text-surface-600 cursor-pointer">Confidentialité</span>
            <span className="hover:text-surface-600 cursor-pointer">Mentions IA</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
