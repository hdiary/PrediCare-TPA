import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle2 } from 'lucide-react';
import { Button, Card, Input, Spinner } from '@/components/ui';
import { api } from '@/lib/api';
import type { AdminUserCreatePayload, CreatedUserCredentials, UserReferences } from '@/lib/types';

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

export function AdminUserCreatePage() {
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [created, setCreated] = useState<CreatedUserCredentials | null>(null);
  const [references, setReferences] = useState<UserReferences | null>(null);
  const [referencesError, setReferencesError] = useState('');

  useEffect(() => {
    if (form.role !== 'professionnel_sante' || references) return;
    api.getUserReferences()
      .then(setReferences)
      .catch((cause) => setReferencesError(cause instanceof Error ? cause.message : 'Impossible de charger les prestataires.'));
  }, [form.role, references]);

  const updateForm = <K extends keyof AdminUserCreatePayload>(
    key: K,
    value: AdminUserCreatePayload[K],
  ) => setForm((current) => ({ ...current, [key]: value }));

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      setCreated(await api.createUser(form));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Impossible de créer le compte.');
    } finally {
      setSaving(false);
    }
  };

  if (created) {
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <Card className="space-y-5 p-6">
          <div className="flex items-center gap-3 text-success-700 dark:text-success-300">
            <CheckCircle2 className="h-6 w-6" />
            <h2 className="text-xl font-bold">Compte créé avec succès</h2>
          </div>
          <p className="text-sm text-surface-600 dark:text-surface-300">
            Notez ces informations et transmettez-les à l’utilisateur. Le mot de passe provisoire ne sera plus affiché après avoir quitté cette page.
          </p>
          <dl className="grid gap-4 rounded-xl bg-surface-50 p-4 text-sm dark:bg-surface-800 sm:grid-cols-2">
            <div>
              <dt className="text-surface-500 dark:text-surface-400">ID utilisateur</dt>
              <dd className="mt-1 font-mono font-semibold text-surface-800 dark:text-surface-100">{created.user_id}</dd>
            </div>
            <div>
              <dt className="text-surface-500 dark:text-surface-400">Identifiant de connexion</dt>
              <dd className="mt-1 break-all font-mono font-semibold text-surface-800 dark:text-surface-100">{created.identifier}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-surface-500 dark:text-surface-400">Mot de passe provisoire</dt>
              <dd className="mt-1 break-all font-mono font-semibold text-surface-800 dark:text-surface-100">{created.temporary_password}</dd>
            </div>
          </dl>
          {created.email_sent ? (
            <p role="status" className="text-sm text-success-700 dark:text-success-300">
              Les identifiants ont été envoyés par e-mail.
            </p>
          ) : (
            <p role="status" className="text-sm text-danger-700 dark:text-danger-300">
              Aucun e-mail n’a été envoyé. {form.email ? 'Vérifiez la configuration e-mail et transmettez les identifiants à l’utilisateur.' : 'L’utilisateur n’a pas fourni d’adresse e-mail : transmettez-lui les identifiants.'}
            </p>
          )}
          <Button onClick={() => navigate('/admin/utilisateurs')}>
            <ArrowLeft className="h-4 w-4" /> Retour aux utilisateurs
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Button variant="outline" onClick={() => navigate('/admin/utilisateurs')}>
          <ArrowLeft className="h-4 w-4" /> Retour aux utilisateurs
        </Button>
        <h2 className="mt-5 text-xl font-bold text-surface-800 dark:text-surface-100">Créer un utilisateur</h2>
        <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
          Crée un compte utilisateur avec son rôle et, pour un professionnel de santé, son prestataire de rattachement.
        </p>
      </div>

      <Card className="p-6">
        {error && (
          <p role="alert" className="mb-4 rounded-xl border border-danger-200 bg-danger-50 p-3 text-sm text-danger-700 dark:border-danger-800 dark:bg-danger-900/20 dark:text-danger-300">
            {error}
          </p>
        )}
        <form onSubmit={submit} className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-200">
              Type d’utilisateur *
              <select
                required
                value={form.role}
                onChange={(event) => {
                  const role = event.target.value as AdminUserCreatePayload['role'];
                  setForm((current) => ({ ...current, role, prestataire_id: undefined }));
                }}
                className="mt-2 h-11 w-full rounded-xl border border-surface-300 bg-white px-3.5 text-sm text-surface-800 dark:border-surface-600 dark:bg-surface-900 dark:text-surface-100"
              >
                <option value="assure">Assuré</option>
                <option value="professionnel_sante">Professionnel de santé</option>
                <option value="gestionnaire">Gestionnaire</option>
                <option value="administrateur">Administrateur</option>
              </select>
            </label>
            {form.role === 'professionnel_sante' && (
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-200">
                Prestataire de rattachement *
                <select
                  required
                  value={form.prestataire_id ?? ''}
                  onChange={(event) => updateForm('prestataire_id', event.target.value || undefined)}
                  className="mt-2 h-11 w-full rounded-xl border border-surface-300 bg-white px-3.5 text-sm text-surface-800 dark:border-surface-600 dark:bg-surface-900 dark:text-surface-100"
                >
                  <option value="">Sélectionner un prestataire</option>
                  {(references?.prestataires ?? []).map((prestataire) => (
                    <option key={prestataire.prestataire_id} value={prestataire.prestataire_id}>
                      {prestataire.nom} — {prestataire.ville} ({prestataire.prestataire_id})
                    </option>
                  ))}
                </select>
                {referencesError && <span role="alert" className="mt-1 block text-xs text-danger-600">{referencesError}</span>}
                {references && references.prestataires.length === 0 && (
                  <span role="alert" className="mt-1 block text-xs text-danger-600">Aucun prestataire actif disponible.</span>
                )}
              </label>
            )}
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
            <Input label="Nom" required value={form.nom} onChange={(event) => updateForm('nom', event.target.value)} />
            <Input label="Prénoms" required value={form.prenoms} onChange={(event) => updateForm('prenoms', event.target.value)} />
            <Input label="Date de naissance" type="date" required value={form.date_naissance} onChange={(event) => updateForm('date_naissance', event.target.value)} />
            <Input label="Téléphone" required value={form.telephone} onChange={(event) => updateForm('telephone', event.target.value)} />
            <Input label="Adresse e-mail (facultative)" type="email" value={form.email} onChange={(event) => updateForm('email', event.target.value)} />
            <Input label="N° CIN (facultatif, 12 chiffres)" pattern="\d{12}" maxLength={12} value={form.numero_cin} onChange={(event) => updateForm('numero_cin', event.target.value)} />
            <Input label="Adresse" required value={form.adresse} onChange={(event) => updateForm('adresse', event.target.value)} />
            <Input label="Ville" required value={form.ville} onChange={(event) => updateForm('ville', event.target.value)} />
          </div>
          <p className="text-xs text-surface-500 dark:text-surface-400">
            Les informations personnelles sont chiffrées. Un identifiant et un mot de passe provisoire seront générés. Si une adresse e-mail est fournie, les identifiants y seront envoyés.
          </p>
          <Button type="submit" disabled={saving}>
            {saving ? <><Spinner className="h-4 w-4" /> Création...</> : 'Créer le compte'}
          </Button>
        </form>
      </Card>
    </div>
  );
}
