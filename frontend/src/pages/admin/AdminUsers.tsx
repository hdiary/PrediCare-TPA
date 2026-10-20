import { useEffect, useState, type FormEvent } from 'react';
import { Plus, Search, Users } from 'lucide-react';
import { Badge, Button, Card, EmptyState, ErrorState, Input, Skeleton, Spinner } from '@/components/ui';
import { ROLE_LABELS } from '@/lib/format';
import { api, isMock } from '@/lib/api';
import type { AdminUserCreatePayload, Role, UserReferences, UserRow } from '@/lib/types';

const ROLE_BADGE_COLORS: Record<Role, string> = {
  insured: 'bg-primary-100 text-primary-700 dark:bg-primary-800 dark:text-primary-200',
  provider: 'bg-kraft-100 text-kraft-700 dark:bg-kraft-800 dark:text-kraft-200',
  manager: 'bg-success-100 text-success-700 dark:bg-success-800 dark:text-success-200',
  admin: 'bg-danger-100 text-danger-700 dark:bg-danger-800 dark:text-danger-200',
};

const EMPTY_FORM: AdminUserCreatePayload = {
  role: 'assure',
  nom: '',
  prenoms: '',
  sexe: 'F',
  date_naissance: '',
  telephone: '',
  email: '',
  adresse: '',
  ville: '',
  numero_cin: '',
};

export function AdminUsers() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [references, setReferences] = useState<UserReferences>({ assures: [], prestataires: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<AdminUserCreatePayload>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');
  const [createdIdentifier, setCreatedIdentifier] = useState('');

  useEffect(() => {
    Promise.all([
      api.getUsers(),
      isMock('users')
        ? Promise.resolve({ assures: [], prestataires: [] } as UserReferences)
        : api.getUserReferences(),
    ])
      .then(([rows, choices]) => {
        setUsers(rows);
        setReferences(choices);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  const filtered = users.filter((u) => {
    const term = search.toLowerCase();
    const matchSearch = u.pseudonym.toLowerCase().includes(term) ||
      u.display_name.toLowerCase().includes(term) || u.email.toLowerCase().includes(term);
    const matchRole = roleFilter === 'all' || u.role === roleFilter;
    return matchSearch && matchRole;
  });

  const updateForm = <K extends keyof AdminUserCreatePayload>(
    key: K,
    value: AdminUserCreatePayload[K],
  ) => setForm((current) => ({ ...current, [key]: value }));

  const openCreateForm = () => {
    setCreatedIdentifier('');
    setFormError('');
    setForm(EMPTY_FORM);
    setCreateOpen(true);
  };

  const createUser = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError('');
    setSaving(true);
    try {
      const created = await api.createUser(form);
      setCreatedIdentifier(created.pseudonym);
      setUsers((current) => [...current, created]);
      setCreateOpen(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Impossible de créer le compte.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Skeleton className="h-96" />;
  if (error) return <ErrorState message="Impossible de charger les utilisateurs." />;

  const selectedAssure = references.assures.find((item) => item.assure_id === form.assure_id);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-1">Utilisateurs</h2>
          <p className="text-sm text-surface-500 dark:text-surface-400">
            Comptes utilisateurs et identifiants pseudonymisés.
          </p>
        </div>
        {!isMock('users') && (
          <Button onClick={openCreateForm}>
            <Plus className="w-4 h-4" /> Créer un compte
          </Button>
        )}
      </div>

      {createdIdentifier && (
        <div role="status" className="rounded-xl border border-success-200 bg-success-50 p-4 text-sm text-success-700 dark:border-success-800 dark:bg-success-900/20 dark:text-success-300">
          Compte créé. L’identifiant <strong className="font-mono">{createdIdentifier}</strong> et le mot de passe provisoire ont été envoyés par e-mail.
        </div>
      )}

      {createOpen && (
        <Card className="p-6">
          <h3 className="mb-5 text-lg font-semibold text-surface-800 dark:text-surface-100">Nouveau compte</h3>
          {formError && (
            <p role="alert" className="mb-4 rounded-xl border border-danger-200 bg-danger-50 p-3 text-sm text-danger-700 dark:border-danger-800 dark:bg-danger-900/20 dark:text-danger-300">
              {formError}
            </p>
          )}
          <form onSubmit={createUser} className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-200">
                Rôle *
                <select
                  required
                  value={form.role}
                  onChange={(event) => setForm({
                    ...EMPTY_FORM,
                    role: event.target.value as AdminUserCreatePayload['role'],
                    nom: form.nom,
                    prenoms: form.prenoms,
                    sexe: form.sexe,
                    date_naissance: form.date_naissance,
                    telephone: form.telephone,
                    email: form.email,
                    adresse: form.adresse,
                    ville: form.ville,
                    numero_cin: form.numero_cin,
                  })}
                  className="mt-2 h-11 w-full rounded-xl border border-surface-300 bg-white px-3.5 text-sm text-surface-800 dark:border-surface-600 dark:bg-surface-900 dark:text-surface-100"
                >
                  <option value="assure">Assuré</option>
                  <option value="professionnel_sante">Professionnel de santé</option>
                  <option value="gestionnaire">Gestionnaire</option>
                  <option value="administrateur">Administrateur</option>
                </select>
              </label>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-200">
                Sexe *
                <select
                  required
                  value={form.sexe}
                  onChange={(event) => updateForm('sexe', event.target.value as 'F' | 'M')}
                  className="mt-2 h-11 w-full rounded-xl border border-surface-300 bg-white px-3.5 text-sm text-surface-800 dark:border-surface-600 dark:bg-surface-900 dark:text-surface-100"
                >
                  <option value="F">Féminin</option>
                  <option value="M">Masculin</option>
                </select>
              </label>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Nom" required value={form.nom} onChange={(event) => updateForm('nom', event.target.value)} />
              <Input label="Prénoms" required value={form.prenoms} onChange={(event) => updateForm('prenoms', event.target.value)} />
              <Input label="Date de naissance" type="date" required value={form.date_naissance} onChange={(event) => updateForm('date_naissance', event.target.value)} />
              <Input label="Téléphone" required value={form.telephone} onChange={(event) => updateForm('telephone', event.target.value)} />
              <Input label="Adresse e-mail" type="email" required value={form.email} onChange={(event) => updateForm('email', event.target.value)} />
              <Input label="N° CIN (12 chiffres)" required pattern="\d{12}" maxLength={12} value={form.numero_cin} onChange={(event) => updateForm('numero_cin', event.target.value)} />
              <Input label="Adresse" required value={form.adresse} onChange={(event) => updateForm('adresse', event.target.value)} />
              <Input label="Ville" required value={form.ville} onChange={(event) => updateForm('ville', event.target.value)} />
            </div>

            {form.role === 'assure' && (
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-200">
                Fiche assuré existante *
                <select
                  required
                  value={form.assure_id || ''}
                  onChange={(event) => setForm((current) => ({
                    ...current,
                    assure_id: event.target.value || undefined,
                    prestataire_id: undefined,
                  }))}
                  className="mt-2 h-11 w-full rounded-xl border border-surface-300 bg-white px-3.5 text-sm text-surface-800 dark:border-surface-600 dark:bg-surface-900 dark:text-surface-100"
                >
                  <option value="">Sélectionner un assuré</option>
                  {references.assures.map((item) => (
                    <option key={item.assure_id} value={item.assure_id}>
                      {item.assure_id} — {item.contrat_id} — {item.rang_beneficiaire}
                    </option>
                  ))}
                </select>
                {selectedAssure && (
                  <span className="mt-1 block text-xs text-surface-500">
                    Contrat {selectedAssure.contrat_id}, rang {selectedAssure.rang_beneficiaire}
                  </span>
                )}
              </label>
            )}
            {form.role === 'professionnel_sante' && (
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-200">
                Prestataire existant *
                <select
                  required
                  value={form.prestataire_id || ''}
                  onChange={(event) => setForm((current) => ({
                    ...current,
                    prestataire_id: event.target.value || undefined,
                    assure_id: undefined,
                  }))}
                  className="mt-2 h-11 w-full rounded-xl border border-surface-300 bg-white px-3.5 text-sm text-surface-800 dark:border-surface-600 dark:bg-surface-900 dark:text-surface-100"
                >
                  <option value="">Sélectionner un prestataire</option>
                  {references.prestataires.map((item) => (
                    <option key={item.prestataire_id} value={item.prestataire_id}>
                      {item.prestataire_id} — {item.nom} — {item.ville}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <p className="text-xs text-surface-500 dark:text-surface-400">
              L’identifiant est calculé à partir du CIN. Les champs personnels sont chiffrés et un mot de passe provisoire de 16 caractères sera envoyé à l’adresse indiquée.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button type="submit" disabled={saving}>
                {saving ? <><Spinner className="w-4 h-4" /> Création...</> : 'Créer le compte'}
              </Button>
              <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={saving}>
                Annuler
              </Button>
            </div>
          </form>
        </Card>
      )}

      <div className="flex flex-col gap-3 md:flex-row">
        <div className="flex-1">
          <Input
            placeholder="Rechercher par identifiant, e-mail ou nom d’affichage..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            icon={<Search className="w-4 h-4" />}
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
          <EmptyState icon={<Users className="w-8 h-8" />} title="Aucun utilisateur" description="Aucun utilisateur ne correspond à vos critères." />
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
