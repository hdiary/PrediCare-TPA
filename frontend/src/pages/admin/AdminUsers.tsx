import { useState, useEffect } from 'react';
import { Users, Search } from 'lucide-react';
import { Card, Badge, Skeleton, ErrorState, EmptyState, Input } from '@/components/ui';
import { ROLE_LABELS } from '@/lib/format';
import { MOCK_ACCOUNTS } from '@/lib/mockData';
import type { Role } from '@/lib/types';

const ROLE_BADGE_COLORS: Record<Role, string> = {
  insured: 'bg-primary-100 text-primary-700 dark:bg-primary-800 dark:text-primary-200',
  provider: 'bg-kraft-100 text-kraft-700 dark:bg-kraft-800 dark:text-kraft-200',
  manager: 'bg-success-100 text-success-700 dark:bg-success-800 dark:text-success-200',
  admin: 'bg-danger-100 text-danger-700 dark:bg-danger-800 dark:text-danger-200',
};

interface UserRow {
  pseudonym: string;
  display_name: string;
  role: Role;
  email: string;
  status: 'active' | 'inactive';
}

const mockUsers: UserRow[] = MOCK_ACCOUNTS.map((acc) => ({
  pseudonym: acc.pseudonym,
  display_name: acc.display_name,
  role: acc.role,
  email: acc.email,
  status: 'active' as const,
}));

// Add a few more mock users
mockUsers.push(
  { pseudonym: 'GST-0008', display_name: 'Gestionnaire A', role: 'manager', email: 'gst8@predicare.fr', status: 'active' },
  { pseudonym: 'GST-0011', display_name: 'Gestionnaire B', role: 'manager', email: 'gst11@predicare.fr', status: 'inactive' },
  { pseudonym: 'PRS-0052', display_name: 'Praticien B', role: 'provider', email: 'prs52@predicare.fr', status: 'active' },
  { pseudonym: 'PRS-0078', display_name: 'Praticien C', role: 'provider', email: 'prs78@predicare.fr', status: 'active' },
  { pseudonym: 'ASS-004218', display_name: 'Assuré B', role: 'insured', email: 'ass4218@predicare.fr', status: 'active' },
  { pseudonym: 'ASS-004219', display_name: 'Assuré C', role: 'insured', email: 'ass4219@predicare.fr', status: 'active' },
);

export function AdminUsers() {
  const [users] = useState<UserRow[]>(mockUsers);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');

  const filtered = users.filter((u) => {
    const matchSearch = u.pseudonym.toLowerCase().includes(search.toLowerCase()) ||
      u.display_name.toLowerCase().includes(search.toLowerCase());
    const matchRole = roleFilter === 'all' || u.role === roleFilter;
    return matchSearch && matchRole;
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-1">Utilisateurs</h2>
        <p className="text-sm text-surface-500 dark:text-surface-400">Comptes utilisateurs (pseudonymes uniquement).</p>
      </div>

      <div className="flex flex-col md:flex-row gap-3">
        <div className="flex-1">
          <Input
            placeholder="Rechercher par pseudonyme ou nom d'affichage..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            icon={<Search className="w-4 h-4" />}
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-900 text-surface-700 dark:text-surface-200 px-4 py-2.5 text-sm focus:border-primary-500"
        >
          <option value="all">Tous les rôles</option>
          <option value="insured">Assurés</option>
          <option value="provider">Professionnels</option>
          <option value="manager">Gestionnaires</option>
          <option value="admin">Administrateurs</option>
        </select>
      </div>

      <Card className="overflow-hidden">
        {filtered.length === 0 ? (
          <EmptyState
            icon={<Users className="w-8 h-8" />}
            title="Aucun utilisateur"
            description="Aucun utilisateur ne correspond à vos critères."
          />
        ) : (
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full">
              <thead>
                <tr className="bg-surface-100 dark:bg-surface-700/50 text-left text-xs font-semibold text-surface-500 dark:text-surface-300 uppercase tracking-wider">
                  <th className="px-6 py-3">Pseudonyme</th>
                  <th className="px-6 py-3">Nom d'affichage</th>
                  <th className="px-6 py-3">Rôle</th>
                  <th className="px-6 py-3">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-300/60 dark:divide-surface-700/60">
                {filtered.map((user) => (
                  <tr key={user.pseudonym} className="hover:bg-surface-50 dark:hover:bg-surface-700/50 transition-colors">
                    <td className="px-6 py-4 text-sm font-mono font-medium text-surface-700 dark:text-surface-200">{user.pseudonym}</td>
                    <td className="px-6 py-4 text-sm text-surface-600 dark:text-surface-300">{user.display_name}</td>
                    <td className="px-6 py-4">
                      <Badge className={ROLE_BADGE_COLORS[user.role]}>{ROLE_LABELS[user.role]}</Badge>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 text-sm ${user.status === 'active' ? 'text-success-600' : 'text-surface-400'}`}>
                        <span className={`w-2 h-2 rounded-full ${user.status === 'active' ? 'bg-success-500' : 'bg-surface-300 dark:bg-surface-600'}`} />
                        {user.status === 'active' ? 'Actif' : 'Inactif'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
