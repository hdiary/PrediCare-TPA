import { useState, type FormEvent } from 'react';
import { AlertCircle, KeyRound } from 'lucide-react';
import { Button, Card, Spinner } from '@/components/ui';
import { PasswordField, PasswordRules } from '@/components/PasswordField';
import { useToast } from '@/components/ui/Toast';
import { api, userErrorMessage } from '@/lib/api';
import { isPasswordValid, passwordChecks } from '@/lib/password';

export function ChangePasswordPage() {
  const { showToast } = useToast();
  const [currentPassword, setCurrentPassword] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    if (!isPasswordValid(password)) {
      setError('Choisissez un nouveau mot de passe conforme aux règles affichées.');
      return;
    }
    if (password !== confirm) {
      setError('Les deux nouveaux mots de passe ne correspondent pas.');
      return;
    }
    setSaving(true);
    try {
      await api.changePassword(currentPassword, password);
      setCurrentPassword('');
      setPassword('');
      setConfirm('');
      showToast('Mot de passe modifié.', 'success');
    } catch (cause) {
      setError(userErrorMessage(cause, 'Impossible de modifier le mot de passe. Vérifiez le mot de passe actuel puis réessayez.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h2 className="mb-1 text-xl font-bold text-surface-800 dark:text-surface-100">Sécurité du compte</h2>
        <p className="text-sm text-surface-500 dark:text-surface-400">Modifiez votre mot de passe à tout moment.</p>
      </div>
      <Card className="p-6 sm:p-8">
        <form onSubmit={submit} className="space-y-5">
          {error && <div role="alert" className="flex items-start gap-2 rounded-xl border border-danger-200 bg-danger-50 p-3 text-sm text-danger-700 dark:border-danger-800 dark:bg-danger-900/30 dark:text-danger-300"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
          <PasswordField id="current-password" label="Mot de passe actuel" value={currentPassword} onChange={setCurrentPassword} autoComplete="current-password" />
          <div>
            <PasswordField id="new-password" label="Nouveau mot de passe" value={password} onChange={setPassword} autoComplete="new-password" />
            <PasswordRules checks={passwordChecks(password)} visible={password.length > 0} />
          </div>
          <PasswordField id="confirm-password" label="Confirmer le nouveau mot de passe" value={confirm} onChange={setConfirm} autoComplete="new-password" />
          <div className="flex justify-end">
            <Button type="submit" disabled={saving || !currentPassword || !password || !confirm}>
              {saving ? <><Spinner className="h-4 w-4" /> Enregistrement...</> : <><KeyRound className="h-4 w-4" /> Modifier le mot de passe</>}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}