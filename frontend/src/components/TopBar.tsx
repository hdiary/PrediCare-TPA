import { useState, useEffect } from 'react';
import { Menu, Bell, Moon, Sun, X, LogOut } from 'lucide-react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useTheme } from '@/lib/theme';
import { useAuth } from '@/lib/auth';
import { Logo } from './Logo';
import { NAV_BY_ROLE } from './Sidebar';
import { ROLE_LABELS } from '@/lib/format';
import type { Role } from '@/lib/types';
import type { ReactNode } from 'react';

const PAGE_TITLES: Record<string, string> = {
  '/assurant': 'Mon assistant',
  '/assurant/remboursements': 'Mes remboursements',
  '/assurant/aide': 'Aide',
  '/professionnel': 'Déposer une facture',
  '/professionnel/factures': 'Mes factures',
  '/professionnel/assistant': 'Assistant RAG',
  '/professionnel/aide': 'Aide',
  '/gestionnaire': 'Tableau de bord',
  '/gestionnaire/alertes': 'Alertes',
  '/gestionnaire/ordonnances': 'Ordonnances',
  '/gestionnaire/aide': 'Aide',
  '/admin': 'Supervision',
  '/admin/configuration': 'Configuration',
  '/admin/modeles': 'Modèles',
  '/admin/audit': 'Journal d\'audit',
  '/admin/utilisateurs': 'Utilisateurs',
  '/admin/aide': 'Aide',
};

const MOBILE_NAV_BY_ROLE: Record<Role, { to: string; label: string; icon: ReactNode }[]> = {
  insured: [
    { to: '/assurant', label: 'Assistant', icon: <span>💬</span> },
    { to: '/assurant/remboursements', label: 'Remboursements', icon: <span>🧾</span> },
  ],
  provider: [
    { to: '/professionnel', label: 'Déposer', icon: <span>📄</span> },
    { to: '/professionnel/factures', label: 'Factures', icon: <span>🧾</span> },
    { to: '/professionnel/assistant', label: 'Assistant', icon: <span>💬</span> },
  ],
  manager: [
    { to: '/gestionnaire', label: 'Tableau', icon: <span>📊</span> },
    { to: '/gestionnaire/alertes', label: 'Alertes', icon: <span>⚠️</span> },
    { to: '/gestionnaire/ordonnances', label: 'Ordonnances', icon: <span>📋</span> },
  ],
  admin: [
    { to: '/admin', label: 'Supervision', icon: <span>🖥️</span> },
    { to: '/admin/configuration', label: 'Config', icon: <span>⚙️</span> },
    { to: '/admin/modeles', label: 'Modèles', icon: <span>🔬</span> },
  ],
};

export function TopBar({ onToggleMobileSidebar }: { onToggleMobileSidebar: () => void }) {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);

  const pageTitle = PAGE_TITLES[location.pathname] || 'PrediCare TPA';

  useEffect(() => {
    setShowMobileMenu(false);
  }, [location.pathname]);

  if (!user) return null;
  const mobileNav = MOBILE_NAV_BY_ROLE[user.role] || [];

  return (
    <>
      <header className="sticky top-0 z-30 bg-surface-50/90 dark:bg-surface-850/90 backdrop-blur border-b border-surface-300/80 dark:border-surface-700 px-4 md:px-8 py-4 flex items-center justify-between gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => { setShowMobileMenu(true); onToggleMobileSidebar(); }}
            aria-label="Ouvrir le menu"
            className="md:hidden p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700 shrink-0"
          >
            <Menu className="w-5 h-5 text-surface-600 dark:text-surface-300" />
          </button>
          <div className="min-w-0">
            <h1 className="text-lg font-medium text-surface-900 dark:text-surface-100 truncate">{pageTitle}</h1>
            <p className="text-xs text-surface-400 hidden md:block">{ROLE_LABELS[user.role]} · {user.pseudonym}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <div className="relative">
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700 relative"
            >
              <Bell className="w-5 h-5 text-surface-600 dark:text-surface-300" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-kraft-500 rounded-full" />
            </button>
            {showNotifications && (
              <div className="absolute right-0 top-12 w-72 max-w-[calc(100vw-2rem)] rounded-3xl bg-white dark:bg-surface-700 border border-primary-100 dark:border-surface-600 shadow-float p-4 z-50">
                <p className="text-sm font-medium text-surface-700 dark:text-surface-200 mb-2">Notifications</p>
                <div className="space-y-2">
                  <div className="text-xs text-surface-500 p-2 rounded-lg bg-surface-50 dark:bg-surface-800">
                    <span className="font-medium text-kraft-700">Nouvelle alerte</span> · ALT-001 · Score 0.92
                  </div>
                  <div className="text-xs text-surface-500 p-2 rounded-lg bg-surface-50 dark:bg-surface-800">
                    <span className="font-medium text-success-600">Facture payée</span> · FAC-2024-1042
                  </div>
                </div>
              </div>
            )}
          </div>

          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700"
          >
            {theme === 'light' ? <Moon className="w-5 h-5 text-surface-600" /> : <Sun className="w-5 h-5 text-surface-300" />}
          </button>
        </div>
      </header>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-30 bg-surface-50 dark:bg-surface-800 border-t border-surface-200 dark:border-surface-700 flex justify-around px-1 py-1.5 pb-[max(0.375rem,env(safe-area-inset-bottom))]">
        {mobileNav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/gestionnaire' || item.to === '/admin' || item.to === '/assurant' || item.to === '/professionnel'}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 flex-1 min-w-0 px-1 py-1.5 rounded-2xl text-xs font-medium ${
                isActive ? 'text-primary-700 dark:text-primary-300' : 'text-surface-400'
              }`
            }
          >
            <span className="text-lg">{item.icon}</span>
            <span className="w-full truncate text-center">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Mobile sidebar overlay */}
      {showMobileMenu && (
        <div className="md:hidden fixed inset-0 z-50 bg-primary-900/40 backdrop-blur-sm" onClick={() => setShowMobileMenu(false)}>
          <div className="absolute left-0 top-0 bottom-0 w-64 max-w-[85vw] bg-white dark:bg-surface-800 p-4 animate-slide-in-right flex flex-col overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <Logo />
              <button onClick={() => setShowMobileMenu(false)}><X className="w-5 h-5 text-surface-400" /></button>
            </div>
            <nav className="flex-1 space-y-1">
              {(NAV_BY_ROLE[user.role] || []).map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/gestionnaire' || item.to === '/admin' || item.to === '/assurant' || item.to === '/professionnel'}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3.5 h-11 rounded-xl text-sm font-medium ${
                      isActive
                        ? 'bg-surface-200 text-surface-900 dark:bg-surface-700 dark:text-white'
                        : 'text-surface-600 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700'
                    }`
                  }
                >
                  {item.icon}
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </nav>
            <button
              onClick={() => { logout(); navigate('/login'); }}
              className="mt-4 flex items-center gap-2 w-full px-3.5 h-11 text-sm text-danger-600 hover:bg-danger-50 dark:hover:bg-danger-900/30 rounded-xl"
            >
              <LogOut className="w-4 h-4" /> Déconnexion
            </button>
          </div>
        </div>
      )}
    </>
  );
}
