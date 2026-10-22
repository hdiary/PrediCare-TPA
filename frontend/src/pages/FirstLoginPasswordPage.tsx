import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { AlertCircle, KeyRound } from 'lucide-react';
import { AuthLayout } from '@/components/AuthLayout';
import { PasswordField, PasswordRules } from '@/components/PasswordField';
import { Button, Spinner } from '@/components/ui';
import { useAuth, getRoleHome } from '@/lib/auth';
import { api, userErrorMessage } from '@/lib/api';
import { isPasswordValid, passwordChecks } from '@/lib/password';

export function FirstLoginPasswordPage() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [choice, setChoice] = useState<'change' | 'keep'>('change');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    if (choice === 'change' && !isPasswordValid(password)) {
      setError('Choisissez un mot de passe conforme aux règles affichées.');
      return;
    }
    if (choice === 'change' && password !== confirm) {
      setError('Les deux mots de passe ne correspondent pas.');
      return;
    }
    setSaving(true);
    try {
      await api.completeFirstLoginPassword({
        keepCurrentPassword: choice === 'keep',
        ...(choice === 'change' ? { newPassword: password } : {}),
      });
      const refreshed = await refreshUser();
      navigate(getRoleHome(refreshed.role), { replace: true });
    } catch (cause) {
      setError(userErrorMessage(cause, 'Impossible d’enregistrer votre choix. Réessayez.'));
    } finally {
      setSaving(false);
    }
  };

  if (!user) return <Navigate to="/login" replace />;
  if (!user.must_change_password) return <Navigate to={getRoleHome(user.role)} replace />;

  return (
    <AuthLayout
      title="Première connexion"
      subtitle="Votre administrateur vous a remis un mot de passe provisoire. Choisissez maintenant de le remplacer ou de le garder."
    >
      {error && (
        <div role="alert" className="mb-4 flex items-start gap-2 rounded-xl border border-danger-200 bg-danger-50 p-3 text-sm text-danger-700 dark:border-danger-800 dark:bg-danger-900/30 dark:text-danger-300">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}
        </div>
      )}
      <form onSubmit={submit} className="space-y-5">
        <fieldset className="space-y-3">
          <legend className="mb-2 text-sm font-medium text-surface-700 dark:text-surface-200">Que souhaitez-vous faire ?</legend>
          <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-surface-300 p-3 dark:border-surface-600">
            <input type="radio" name="password-choice" checked={choice === 'change'} onChange={() => setChoice('change')} className="mt-1 accent-primary-700" />
            <span><span className="block text-sm font-medium text-surface-800 dark:text-surface-100">Choisir un nouveau mot de passe</span><span className="mt-1 block text-xs text-surface-500 dark:text-surface-400">Recommandé pour sécuriser votre compte.</span></span>
          </label>
          <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-surface-300 p-3 dark:border-surface-600">
            <input type="radio" name="password-choice" checked={choice === 'keep'} onChange={() => setChoice('keep')} className="mt-1 accent-primary-700" />
            <span><span className="block text-sm font-medium text-surface-800 dark:text-surface-100">Garder le mot de passe provisoire</span><span className="mt-1 block text-xs text-surface-500 dark:text-surface-400">Vous pourrez le modifier plus tard dans votre compte.</span></span>
          </label>
        </fieldset>
        {choice === 'change' && (
          <div className="space-y-4">
            <div>
              <PasswordField id="first-password" label="Nouveau mot de passe" value={password} onChange={setPassword} autoComplete="new-password" />
              <PasswordRules checks={passwordChecks(password)} visible={password.length > 0} />
            </div>
            <PasswordField id="confirm-first-password" label="Confirmer le mot de passe" value={confirm} onChange={setConfirm} autoComplete="new-password" />
          </div>
        )}
        <Button type="submit" size="lg" className="w-full" disabled={saving}>
          {saving ? <><Spinner className="h-4 w-4" /> Enregistrement...</> : <><KeyRound className="h-4 w-4" /> Continuer</>}
        </Button>
      </form>
    </AuthLayout>
  );
}