import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Link2Off } from 'lucide-react';
import { AuthLayout } from '@/components/AuthLayout';
import { PasswordField, PasswordRules } from '@/components/PasswordField';
import { Button, Spinner } from '@/components/ui';
import { api, userErrorMessage } from '@/lib/api';
import { isPasswordValid, passwordChecks } from '@/lib/password';

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token') ?? '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  if (!token) {
    return (
      <AuthLayout title="Lien invalide">
        <div className="flex flex-col items-center text-center gap-4">
          <Link2Off className="w-12 h-12 text-warning-600 dark:text-warning-300" />
          <p className="text-sm text-surface-600 dark:text-surface-300">
            Ce lien de réinitialisation est incomplet ou n'est plus valable.
          </p>
          <Button className="w-full" size="lg" onClick={() => navigate('/mot-de-passe-oublie')}>
            Refaire une demande
          </Button>
        </div>
      </AuthLayout>
    );
  }

  if (done) {
    return (
      <AuthLayout title="Mot de passe modifié">
        <div className="flex flex-col items-center text-center gap-4">
          <CheckCircle2 className="w-12 h-12 text-success-600 dark:text-success-300" />
          <p className="text-sm text-surface-600 dark:text-surface-300">
            Votre mot de passe a été modifié. Vous pouvez maintenant vous connecter avec le nouveau.
          </p>
          <Button className="w-full" size="lg" onClick={() => navigate('/login')}>
            Se connecter
          </Button>
        </div>
      </AuthLayout>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!isPasswordValid(password)) {
      setError('Le mot de passe ne respecte pas toutes les règles.');
      return;
    }
    if (confirm !== password) {
      setError('Les mots de passe ne correspondent pas.');
      return;
    }
    setLoading(true);
    try {
      await api.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(userErrorMessage(err, 'Impossible de modifier le mot de passe. Vérifiez le lien puis réessayez.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Nouveau mot de passe"
      subtitle="Choisissez un mot de passe que vous n'utilisez nulle part ailleurs."
      footer={<Link to="/login" className="text-primary-700 dark:text-primary-400 underline">Retour à la connexion</Link>}
    >
      {error && (
        <div className="mb-4 flex items-start gap-2 p-3 rounded-2xl bg-danger-50 dark:bg-danger-900/30 border border-danger-200 dark:border-danger-800 text-sm text-danger-700 dark:text-danger-300">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <PasswordField id="new-password" label="Nouveau mot de passe" value={password} onChange={setPassword} autoComplete="new-password" />
          <PasswordRules checks={passwordChecks(password)} visible={password.length > 0} />
        </div>
        <PasswordField id="confirm-password" label="Confirmer le mot de passe" value={confirm} onChange={setConfirm} autoComplete="new-password" />
        <Button type="submit" className="w-full" size="lg" disabled={loading}>
          {loading ? (<><Spinner className="w-4 h-4" /> Enregistrement...</>) : 'Modifier le mot de passe'}
        </Button>
      </form>
    </AuthLayout>
  );
}
