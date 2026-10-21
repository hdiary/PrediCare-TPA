import { useState, useEffect } from 'react';
import { Menu, Bell, Moon, Sun, X, LogOut, KeyRound } from 'lucide-react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useTheme } from '@/lib/theme';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import { formatDateTime, formatMGA, INVOICE_STATUS_LABELS } from '@/lib/format';
import { Logo } from './Logo';
import { NAV_BY_ROLE } from './Sidebar';
import { ROLE_LABELS } from '@/lib/format';
import type { Role } from '@/lib/types';
import type { ReactNode } from 'react';

interface WorkspaceNotification {
  id: string;
  title: string;
  detail: string;
  date: string;
  href: string;
}

const PAGE_TITLES: Record<string, string> = {
  '/assurant': 'Mon assistant',
  '/assurant/remboursements': 'Mes remboursements',
  '/assurant/mot-de-passe': 'Sécurité du compte',
  '/assurant/aide': 'Aide',
  '/professionnel': 'Déposer une facture',
  '/professionnel/factures': 'Mes factures',
  '/professionnel/mot-de-passe': 'Sécurité du compte',
  '/professionnel/assistant': 'Assistant RAG',
  '/professionnel/aide': 'Aide',
  '/gestionnaire': 'Tableau de bord',
  '/gestionnaire/alertes': 'Alertes',
  '/gestionnaire/mot-de-passe': 'Sécurité du compte',
  '/gestionnaire/ordonnances': 'Ordonnances',
  '/gestionnaire/corpus-rag': 'Corpus documentaire RAG',
  '/gestionnaire/aide': 'Aide',
  '/admin': 'Supervision',
  '/admin/configuration': 'Configuration',
  '/admin/modeles': 'Modèles',
  '/admin/audit': 'Journal d\'audit',
  '/admin/utilisateurs': 'Utilisateurs',
  '/admin/mot-de-passe': 'Sécurité du compte',
  '/admin/aide': 'Aide',
};

const MOBILE_NAV_BY_ROLE: Record<Role, { to: string; label: string; icon: ReactNode }[]> = {
  insured: [
    { to: '/assurant', label: 'Assistant', icon: <span>💬</span> },
    { to: '/assurant/remboursements', label: 'Remboursements', icon: <span>🧾</span> },
    { to: '/assurant/mot-de-passe', label: 'Sécurité', icon: <KeyRound className="h-4 w-4" /> },
  ],
  provider: [
    { to: '/professionnel', label: 'Déposer', icon: <span>📄</span> },
    { to: '/professionnel/factures', label: 'Factures', icon: <span>🧾</span> },
    { to: '/professionnel/assistant', label: 'Assistant', icon: <span>💬</span> },
    { to: '/professionnel/mot-de-passe', label: 'Sécurité', icon: <KeyRound className="h-4 w-4" /> },
  ],
  manager: [
    { to: '/gestionnaire', label: 'Tableau', icon: <span>📊</span> },
    { to: '/gestionnaire/alertes', label: 'Alertes', icon: <span>⚠️</span> },
    { to: '/gestionnaire/ordonnances', label: 'Ordonnances', icon: <span>📋</span> },
    { to: '/gestionnaire/corpus-rag', label: 'Documents RAG', icon: <span>📚</span> },
    { to: '/gestionnaire/mot-de-passe', label: 'Sécurité', icon: <KeyRound className="h-4 w-4" /> },
  ],
  admin: [
    { to: '/admin', label: 'Supervision', icon: <span>🖥️</span> },
    { to: '/admin/configuration', label: 'Config', icon: <span>⚙️</span> },
    { to: '/admin/modeles', label: 'Modèles', icon: <span>🔬</span> },
    { to: '/admin/mot-de-passe', label: 'Sécurité', icon: <KeyRound className="h-4 w-4" /> },
  ],
};

export function TopBar({ onToggleMobileSidebar }: { onToggleMobileSidebar: () => void }) {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState<WorkspaceNotification[]>([]);

  const pageTitle = PAGE_TITLES[location.pathname] || 'PrediCare TPA';

  useEffect(() => {
    setShowMobileMenu(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    const refresh = async () => {
      try {
        if (user.role === 'manager' || user.role === 'admin') {
          const result = await api.getAlerts({ status: 'pending' });
          if (active) setNotifications(result.items.slice(0, 5).map((alert) => ({
            id: alert.id,
            title: 'Alerte à examiner',
            detail: `${alert.id} · score ${alert.score.toFixed(2)} · ${formatMGA(alert.amount)}`,
            date: alert.created_at,
            href: user.role === 'manager' ? `/gestionnaire/alertes/${alert.id}` : '/admin',
          })));
          return;
        }
        const result = await api.getInvoices();
        if (active) setNotifications(result.items.slice(0, 5).map((invoice) => ({
          id: invoice.id,
          title: INVOICE_STATUS_LABELS[invoice.status] || 'Mise à jour de facture',
          detail: `${invoice.id} · ${formatMGA(invoice.amount)}`,
          date: invoice.date,
          href: user.role === 'provider' ? '/professionnel/factures' : '/assurant/remboursements',
        })));
      } catch {
        if (active) setNotifications([]);
      }
    };
    void refresh();
    const interval = window.setInterval(() => void refresh(), 60_000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [user]);

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
              aria-label={`Notifications${notifications.length ? `, ${notifications.length} éléments` : ''}`}
              aria-expanded={showNotifications}
              className="p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700 relative"
            >
              <Bell className="w-5 h-5 text-surface-600 dark:text-surface-300" />
              {notifications.length > 0 && <span className="absolute top-1 right-1 min-w-4 h-4 px-1 rounded-full bg-danger-600 text-white text-[10px] leading-4 text-center">{notifications.length}</span>}
            </button>
            {showNotifications && (
              <div className="absolute right-0 top-12 w-80 max-w-[calc(100vw-2rem)] rounded-xl bg-white dark:bg-surface-700 border border-surface-300 dark:border-surface-600 shadow-float p-3 z-50">
                <p className="text-sm font-medium text-surface-700 dark:text-surface-200 px-2 pb-2">Notifications récentes</p>
                {notifications.length === 0 ? (
                  <p className="text-xs text-surface-500 p-3">Aucune notification récente.</p>
                ) : (
                  <div className="max-h-80 overflow-y-auto divide-y divide-surface-200 dark:divide-surface-600">
                    {notifications.map((item) => (
                      <button
                        key={item.id}
                        onClick={() => { setShowNotifications(false); navigate(item.href); }}
                        className="w-full text-left px-2 py-3 hover:bg-surface-50 dark:hover:bg-surface-800"
                      >
                        <span className="block text-xs font-semibold text-surface-700 dark:text-surface-100">{item.title}</span>
                        <span className="block text-xs text-surface-500 mt-1">{item.detail}</span>
                        <span className="block text-[11px] text-surface-400 mt-1">{formatDateTime(item.date)}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={theme === 'light' ? 'Passer au thème sombre' : 'Passer au thème clair'}
            title={theme === 'light' ? 'Passer au thème sombre' : 'Passer au thème clair'}
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
