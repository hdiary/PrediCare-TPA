import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Pencil, Plus, Search, Users, UserX } from 'lucide-react';
import { Badge, Button, Card, EmptyState, ErrorState, Input, ListPagination, Modal, Skeleton } from '@/components/ui';
import { ROLE_LABELS } from '@/lib/format';
import { api, isMock } from '@/lib/api';
import type { AdminAccountRole, Role, UserReferences, UserRow } from '@/lib/types';

const ROLE_BADGE_COLORS: Record<Role, string> = {
  insured: 'bg-primary-100 text-primary-700 dark:bg-primary-800 dark:text-primary-200',
  provider: 'bg-kraft-100 text-kraft-700 dark:bg-kraft-800 dark:text-kraft-200',
  manager: 'bg-success-100 text-success-700 dark:bg-success-800 dark:text-success-200',
  admin: 'bg-danger-100 text-danger-700 dark:bg-danger-800 dark:text-danger-200',
};

const ROLE_TO_ADMIN: Record<Role, AdminAccountRole> = {
  insured: 'assure',
  provider: 'professionnel_sante',
  manager: 'gestionnaire',
  admin: 'administrateur',
};

export function AdminUsers() {
  const navigate = useNavigate();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<Role | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<'active' | 'inactive' | 'all'>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [editing, setEditing] = useState<UserRow | null>(null);
  const [deactivating, setDeactivating] = useState<UserRow | null>(null);
  const [references, setReferences] = useState<UserReferences | null>(null);
  const [referencesError, setReferencesError] = useState('');
  const [editRole, setEditRole] = useState<Role>('insured');
  const [editActive, setEditActive] = useState(true);
  const [editAssureId, setEditAssureId] = useState('');
  const [editPrestataireId, setEditPrestataireId] = useState('');
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState('');

  const load = () => {
    setLoading(true);
    setError(false);
    api.getUsers({
      role: roleFilter,
      status: statusFilter,
      search,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    }).then((data) => {
      if (page > 1 && (page - 1) * pageSize >= data.total) {
        setPage(Math.max(1, Math.ceil(data.total / pageSize)));
        return;
      }
      setUsers(data.items);
      setTotal(data.total);
    }).catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, [page, pageSize, roleFilter, search, statusFilter]);

  const changeRoleFilter = (role: Role | 'all') => {
    setRoleFilter(role);
    setPage(1);
  };

  const changeStatusFilter = (status: 'active' | 'inactive' | 'all') => {
    setStatusFilter(status);
    setPage(1);
  };

  const openEdit = async (user: UserRow) => {
    if (!user.user_id) return;
    setActionError('');
    setReferencesError('');
    setEditing(user);
    setEditRole(user.role);
    setEditActive(user.status === 'active');
    setEditAssureId(user.assure_id ?? '');
    setEditPrestataireId(user.prestataire_id ?? '');
    if (!references) {
      try {
        setReferences(await api.getUserReferences());
      } catch (cause) {
        setReferencesError(cause instanceof Error ? cause.message : 'Impossible de charger les référentiels.');
      }
    }
  };

  const saveEdit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editing?.user_id) return;
    setSaving(true);
    setActionError('');
    try {
      await api.updateUser(editing.user_id, {
        role: editRole,
        is_active: editActive,
        assure_id: editRole === 'insured' ? editAssureId || null : null,
        prestataire_id: editRole === 'provider' ? editPrestataireId || null : null,
      });
      setEditing(null);
      load();
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : 'Impossible de modifier le compte.');
    } finally {
      setSaving(false);
    }
  };

  const deactivate = async () => {
    if (!deactivating?.user_id) return;
    setSaving(true);
    setActionError('');
    try {
      await api.deactivateUser(deactivating.user_id);
      setDeactivating(null);
      load();
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : 'Impossible de désactiver le compte.');
    } finally {
      setSaving(false);
    }
  };

  const onPageSizeChange = (size: number) => {
    setPageSize(size);
    setPage(1);
  };

  if (loading && users.length === 0) return <Skeleton className="h-96" />;
  if (error && users.length === 0) return <ErrorState message="Impossible de charger les utilisateurs." onRetry={load} />;

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
            placeholder="Rechercher par identifiant ou e-mail..."
            value={search}
            onChange={(event) => { setSearch(event.target.value); setPage(1); }}
            icon={<Search className="h-4 w-4" />}
          />
        </div>
        <select
          value={roleFilter}
          onChange={(event) => changeRoleFilter(event.target.value as Role | 'all')}
          className="rounded-xl border border-surface-300 bg-white px-4 py-2.5 text-sm text-surface-700 dark:border-surface-600 dark:bg-surface-900 dark:text-surface-200"
        >
          <option value="all">Tous les rôles</option>
          <option value="insured">Assurés</option>
          <option value="provider">Professionnels</option>
          <option value="manager">Gestionnaires</option>
          <option value="admin">Administrateurs</option>
        </select>
        <select
          value={statusFilter}
          onChange={(event) => changeStatusFilter(event.target.value as typeof statusFilter)}
          className="rounded-xl border border-surface-300 bg-white px-4 py-2.5 text-sm text-surface-700 dark:border-surface-600 dark:bg-surface-900 dark:text-surface-200"
        >
          <option value="all">Tous les statuts</option>
          <option value="active">Actifs</option>
          <option value="inactive">Inactifs</option>
        </select>
      </div>

      <Card className="overflow-hidden">
        {error ? (
          <ErrorState message="Impossible de charger les utilisateurs." onRetry={load} />
        ) : loading ? (
          <div className="p-8"><Skeleton className="h-48" /></div>
        ) : users.length === 0 ? (
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
                  {!isMock('users') && <th className="px-6 py-3.5">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-300/60 dark:divide-surface-700/60">
                {users.map((user) => (
                  <tr key={user.user_id ?? user.pseudonym} className="transition-colors hover:bg-surface-50 dark:hover:bg-surface-700/50">
                    <td className="px-6 py-4 font-mono text-sm font-medium text-surface-700 dark:text-surface-200">{user.pseudonym}</td>
                    <td className="px-6 py-4 text-sm text-surface-600 dark:text-surface-300">{user.display_name}</td>
                    <td className="px-6 py-4"><Badge className={ROLE_BADGE_COLORS[user.role]}>{ROLE_LABELS[user.role]}</Badge></td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 text-sm ${user.status === 'active' ? 'text-success-600' : 'text-surface-400'}`}>
                        <span className={`h-2 w-2 rounded-full ${user.status === 'active' ? 'bg-success-500' : 'bg-surface-300 dark:bg-surface-600'}`} />
                        {user.status === 'active' ? 'Actif' : 'Inactif'}
                      </span>
                    </td>
                    {!isMock('users') && (
                      <td className="px-6 py-4">
                        <div className="flex gap-2">
                          <Button variant="outline" size="sm" onClick={() => openEdit(user)}>
                            <Pencil className="h-3.5 w-3.5" /> Modifier
                          </Button>
                          {user.status === 'active' && (
                            <Button variant="danger" size="sm" onClick={() => { setActionError(''); setDeactivating(user); }}>
                              <UserX className="h-3.5 w-3.5" /> Désactiver
                            </Button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!loading && !error && total > 0 && (
          <ListPagination
            page={page}
            pageSize={pageSize}
            total={total}
            onPageChange={setPage}
            onPageSizeChange={onPageSizeChange}
          />
        )}
      </Card>

      <Modal
        open={!!editing}
        onClose={() => { if (!saving) setEditing(null); }}
        title={`Modifier le compte ${editing?.pseudonym ?? ''}`}
        footer={(
          <>
            <Button variant="ghost" disabled={saving} onClick={() => setEditing(null)}>Annuler</Button>
            <Button type="submit" form="edit-user-form" disabled={saving || !!referencesError}>
              {saving ? 'Enregistrement...' : 'Enregistrer'}
            </Button>
          </>
        )}
      >
        <form id="edit-user-form" onSubmit={saveEdit} className="space-y-4">
          {actionError && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-sm text-danger-700 dark:bg-danger-900/20 dark:text-danger-300">{actionError}</p>}
          {referencesError && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-sm text-danger-700 dark:bg-danger-900/20 dark:text-danger-300">{referencesError}</p>}
          <label className="block text-sm font-medium text-surface-700 dark:text-surface-200">
            Rôle
            <select
              value={editRole}
              onChange={(event) => {
                setEditRole(event.target.value as Role);
                setEditAssureId('');
                setEditPrestataireId('');
              }}
              className="mt-2 h-11 w-full rounded-xl border border-surface-300 bg-white px-3.5 text-sm dark:border-surface-600 dark:bg-surface-900"
            >
              {Object.keys(ROLE_TO_ADMIN).map((role) => (
                <option key={role} value={role}>{ROLE_LABELS[role as Role]}</option>
              ))}
            </select>
          </label>
          {editRole === 'provider' && (
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-200">
              Prestataire *
              <select
                required={editActive}
                value={editPrestataireId}
                onChange={(event) => setEditPrestataireId(event.target.value)}
                className="mt-2 h-11 w-full rounded-xl border border-surface-300 bg-white px-3.5 text-sm dark:border-surface-600 dark:bg-surface-900"
              >
                <option value="">Sélectionner un prestataire</option>
                {(references?.prestataires ?? []).map((provider) => (
                  <option key={provider.prestataire_id} value={provider.prestataire_id}>{provider.nom} — {provider.ville}</option>
                ))}
              </select>
            </label>
          )}
          {editRole === 'insured' && (
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-200">
              Assuré {editActive && '*'}
              <select
                required={editActive}
                value={editAssureId}
                onChange={(event) => setEditAssureId(event.target.value)}
                className="mt-2 h-11 w-full rounded-xl border border-surface-300 bg-white px-3.5 text-sm dark:border-surface-600 dark:bg-surface-900"
              >
                <option value="">Sélectionner un assuré</option>
                {(references?.assures ?? []).map((assure) => (
                  <option key={assure.assure_id} value={assure.assure_id}>{assure.assure_id} — contrat {assure.contrat_id}</option>
                ))}
              </select>
            </label>
          )}
          <label className="flex items-center gap-3 text-sm text-surface-700 dark:text-surface-200">
            <input type="checkbox" checked={editActive} onChange={(event) => setEditActive(event.target.checked)} className="h-4 w-4 accent-primary-600" />
            Compte actif
          </label>
          <p className="text-xs text-surface-500 dark:text-surface-400">
            Un compte désactivé peut être réactivé en cochant cette option. La réactivation nécessite le rattachement correspondant au rôle.
          </p>
        </form>
      </Modal>

      <Modal
        open={!!deactivating}
        onClose={() => { if (!saving) setDeactivating(null); }}
        title="Désactiver le compte"
        footer={(
          <>
            <Button variant="ghost" disabled={saving} onClick={() => setDeactivating(null)}>Annuler</Button>
            <Button variant="danger" disabled={saving} onClick={deactivate}>
              {saving ? 'Désactivation...' : 'Désactiver'}
            </Button>
          </>
        )}
      >
        <div className="space-y-3 text-sm text-surface-600 dark:text-surface-300">
          <p>Le compte de <strong>{deactivating?.pseudonym}</strong> sera désactivé sans supprimer son historique.</p>
          <p>Vous pourrez le réactiver ultérieurement depuis la fenêtre de modification.</p>
          {actionError && <p role="alert" className="text-danger-600">{actionError}</p>}
        </div>
      </Modal>
    </div>
  );
}
