import { NavLink, useNavigate } from 'react-router-dom';
import { useState, type ReactNode } from 'react';
import {
  LayoutDashboard, AlertTriangle, FileText, MessageSquare,
  Settings, Server, GitBranch, ScrollText, Users, LogOut,
  ChevronLeft, ChevronRight, HelpCircle, Receipt, ClipboardList, BookOpen,
} from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { Logo } from './Logo';
import { ROLE_LABELS } from '@/lib/format';
import type { Role } from '@/lib/types';

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
}

export const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  insured: [
    { to: '/assurant', label: 'Mon assistant', icon: <MessageSquare className="w-5 h-5" /> },
    { to: '/assurant/remboursements', label: 'Mes remboursements', icon: <Receipt className="w-5 h-5" /> },
    { to: '/assurant/aide', label: 'Aide', icon: <HelpCircle className="w-5 h-5" /> },
  ],
  provider: [
    { to: '/professionnel', label: 'Déposer une facture', icon: <FileText className="w-5 h-5" /> },
    { to: '/professionnel/factures', label: 'Mes factures', icon: <Receipt className="w-5 h-5" /> },
    { to: '/professionnel/assistant', label: 'Assistant RAG', icon: <MessageSquare className="w-5 h-5" /> },
    { to: '/professionnel/aide', label: 'Aide', icon: <HelpCircle className="w-5 h-5" /> },
  ],
  manager: [
    { to: '/gestionnaire', label: 'Tableau de bord', icon: <LayoutDashboard className="w-5 h-5" /> },
    { to: '/gestionnaire/alertes', label: 'Alertes', icon: <AlertTriangle className="w-5 h-5" /> },
    { to: '/gestionnaire/ordonnances', label: 'Ordonnances', icon: <ClipboardList className="w-5 h-5" /> },
    { to: '/gestionnaire/corpus-rag', label: 'Documents RAG', icon: <BookOpen className="w-5 h-5" /> },
    { to: '/gestionnaire/aide', label: 'Aide', icon: <HelpCircle className="w-5 h-5" /> },
  ],
  admin: [
    { to: '/admin', label: 'Supervision', icon: <Server className="w-5 h-5" /> },
    { to: '/admin/configuration', label: 'Configuration', icon: <Settings className="w-5 h-5" /> },
    { to: '/admin/modeles', label: 'Modèles', icon: <GitBranch className="w-5 h-5" /> },
    { to: '/admin/audit', label: 'Journal d\'audit', icon: <ScrollText className="w-5 h-5" /> },
    { to: '/admin/utilisateurs', label: 'Utilisateurs', icon: <Users className="w-5 h-5" /> },
    { to: '/admin/aide', label: 'Aide', icon: <HelpCircle className="w-5 h-5" /> },
  ],
};

export function Sidebar({ collapsed, onToggleCollapse }: { collapsed: boolean; onToggleCollapse: () => void }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [showUserMenu, setShowUserMenu] = useState(false);

  if (!user) return null;
  const items = NAV_BY_ROLE[user.role] || [];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className={`${collapsed ? 'w-20' : 'w-64'} flex-shrink-0 h-screen sticky top-0 bg-surface-100 dark:bg-surface-850 border-r border-surface-300/80 dark:border-surface-700 flex flex-col transition-all duration-300 hidden md:flex`}>
      <div className="flex items-center justify-between px-4 py-4 border-b border-surface-300/60 dark:border-surface-700">
        {collapsed ? <div className="w-10 h-10 mx-auto"><Logo size="sm" /></div> : <Logo />}
        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-700 text-surface-400"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto scrollbar-thin py-4">
        <ul className="space-y-1 px-3">
          {items.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === '/gestionnaire' || item.to === '/admin' || item.to === '/assurant' || item.to === '/professionnel'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 h-11 rounded-xl text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-surface-200 text-surface-900 dark:bg-surface-700 dark:text-white [&>svg]:text-primary-700 dark:[&>svg]:text-primary-400'
                      : 'text-surface-600 dark:text-surface-300 hover:bg-surface-200/60 hover:text-surface-900 dark:hover:bg-surface-700'
                  } ${collapsed ? 'justify-center' : ''}`
                }
                title={collapsed ? item.label : undefined}
              >
                {item.icon}
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="p-3 relative border-t border-surface-300/60 dark:border-surface-700">
        <button
          onClick={() => setShowUserMenu(!showUserMenu)}
          className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-lg hover:bg-surface-200/60 dark:hover:bg-surface-700 transition-all ${collapsed ? 'justify-center' : ''}`}
        >
          <div className="w-9 h-9 rounded-full bg-primary-600 flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
            {user.pseudonym.slice(0, 3)}
          </div>
          {!collapsed && (
            <div className="text-left flex-1 min-w-0">
              <p className="text-sm font-medium text-surface-700 dark:text-surface-200 truncate">{user.pseudonym}</p>
              <p className="text-xs text-surface-400 truncate">{ROLE_LABELS[user.role]}</p>
            </div>
          )}
        </button>
        {showUserMenu && (
          <div className="absolute bottom-16 left-3 right-3 rounded-xl bg-white dark:bg-surface-700 border border-surface-300/80 dark:border-surface-600 shadow-lg p-1 z-50">
            <button onClick={handleLogout} className="flex items-center gap-2 w-full px-3 py-2 text-sm text-danger-600 hover:bg-danger-50 dark:hover:bg-danger-900/30 rounded-lg">
              <LogOut className="w-4 h-4" /> Déconnexion
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
