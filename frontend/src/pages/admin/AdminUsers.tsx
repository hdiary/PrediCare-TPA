import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, Users } from 'lucide-react';
import { Badge, Button, Card, EmptyState, ErrorState, Input, Skeleton } from '@/components/ui';
import { ROLE_LABELS } from '@/lib/format';
import { api, isMock } from '@/lib/api';
import type { Role, UserRow } from '@/lib/types';

const ROLE_BADGE_COLORS: Record<Role, string> = {
  insured: 'bg-primary-100 text-primary-700 dark:bg-primary-800 dark:text-primary-200',
  provider: 'bg-kraft-100 text-kraft-700 dark:bg-kraft-800 dark:text-kraft-200',
  manager: 'bg-success-100 text-success-700 dark:bg-success-800 dark:text-success-200',
  admin: 'bg-danger-100 text-danger-700 dark:bg-danger-800 dark:text-danger-200',
};

export function AdminUsers() {
  const navigate = useNavigate();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');

  useEffect(() => {
    api.getUsers()
      .then(setUsers)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Skeleton className="h-96" />;
  if (error) return <ErrorState message="Impossible de charger les utilisateurs." />;

  const term = search.toLowerCase();
  const filtered = users.filter((user) => (
    (user.pseudonym.toLowerCase().includes(term) ||
      user.display_name.toLowerCase().includes(term) ||
      (user.email ?? '').toLowerCase().includes(term)) &&
    (roleFilter === 'all' || user.role === roleFilter)
  ));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="mb-1 text-xl font-bold text-surface-800 dark:text-surface-100">Utilisateurs</h2>
          <p className="text-sm text-surface-500 dark:text-surface-400">
            Comptes utilisateurs et identifiants pseudonymisés.
          </p>
        </div>
        {!isMock('users') && (
          <Button onClick={() => navigate('/admin/utilisateurs/nouveau')}>
            <Plus className="h-4 w-4" /> Créer un compte
          </Button>
        )}
      </div>

      <div className="flex flex-col gap-3 md:flex-row">
        <div className="flex-1">
          <Input
            placeholder="Rechercher par identifiant, e-mail ou nom d’affichage..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            icon={<Search className="h-4 w-4" />}
          />
        </div>
        <select
          value={roleFilter}
          onChange={(event) => setRoleFilter(event.target.value)}
          className="rounded-xl border border-surface-300 bg-white px-4 py-2.5 text-sm text-surface-700 dark:border-surface-600 dark:bg-surface-900 dark:text-surface-200"
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
          <EmptyState icon={<Users className="h-8 w-8" />} title="Aucun utilisateur" description="Aucun utilisateur ne correspond à vos critères." />
        ) : (
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full">
              <thead>
                <tr className="bg-surface-100 text-left text-xs font-semibold uppercase tracking-wider text-surface-500 dark:bg-surface-700/50 dark:text-surface-300">
                  <th className="px-6 py-3.5">Identifiant</th>
                  <th className="px-6 py-3.5">Nom d’affichage</th>
                  <th className="px-6 py-3.5">Rôle</th>
                  <th className="px-6 py-3.5">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-300/60 dark:divide-surface-700/60">
                {filtered.map((user) => (
                  <tr key={user.pseudonym} className="transition-colors hover:bg-surface-50 dark:hover:bg-surface-700/50">
                    <td className="px-6 py-4 font-mono text-sm font-medium text-surface-700 dark:text-surface-200">{user.pseudonym}</td>
                    <td className="px-6 py-4 text-sm text-surface-600 dark:text-surface-300">{user.display_name}</td>
                    <td className="px-6 py-4"><Badge className={ROLE_BADGE_COLORS[user.role]}>{ROLE_LABELS[user.role]}</Badge></td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 text-sm ${user.status === 'active' ? 'text-success-600' : 'text-surface-400'}`}>
                        <span className={`h-2 w-2 rounded-full ${user.status === 'active' ? 'bg-success-500' : 'bg-surface-300 dark:bg-surface-600'}`} />
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
