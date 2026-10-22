import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, AlertCircle, MailCheck, ArrowLeft } from 'lucide-react';
import { AuthLayout } from '@/components/AuthLayout';
import { Button, Input, Spinner } from '@/components/ui';
import { api, isMock, userErrorMessage } from '@/lib/api';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.requestPasswordReset(email.trim());
      setSent(true);
    } catch (err) {
      setError(userErrorMessage(err, "Impossible d'envoyer la demande. Vérifiez l'adresse puis réessayez."));
    } finally {
      setLoading(false);
    }
  };

  const back = (
    <Link to="/login" className="inline-flex items-center gap-1.5 text-primary-700 dark:text-primary-400 underline">
      <ArrowLeft className="w-4 h-4" /> Retour à la connexion
    </Link>
  );

  if (sent) {
    return (
      <AuthLayout title="Vérifiez votre boîte mail" footer={back}>
        <div className="flex flex-col items-center text-center gap-4">
          <MailCheck className="w-12 h-12 text-primary-600 dark:text-primary-300" />
          <p className="text-sm text-surface-600 dark:text-surface-300">
            Si un compte existe pour <strong>{email}</strong>, un lien de réinitialisation vient d'être envoyé. Ce lien n'est valable qu'un temps limité.
          </p>
          <p className="text-xs text-surface-500 dark:text-surface-400">
            Rien reçu ? Vérifiez vos courriers indésirables, ou refaites une demande.
          </p>
          {isMock('password') && (
            <Link
              to="/reinitialiser-mot-de-passe?token=demo"
              className="w-full text-xs rounded-xl border border-dashed border-surface-300 dark:border-surface-600 p-3 text-surface-600 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700"
            >
              Mode démonstration : aucun e-mail n'est envoyé. Ouvrir la page de réinitialisation →
            </Link>
          )}
          <Button variant="outline" className="w-full" onClick={() => setSent(false)}>
            Refaire une demande
          </Button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Mot de passe oublié"
      subtitle="Saisissez l'adresse e-mail de votre compte pour recevoir un lien. Si votre compte n'a pas d'adresse e-mail, contactez un administrateur pour obtenir un nouveau mot de passe provisoire."
      footer={back}
    >
      {error && (
        <div className="mb-4 flex items-start gap-2 p-3 rounded-2xl bg-danger-50 dark:bg-danger-900/30 border border-danger-200 dark:border-danger-800 text-sm text-danger-700 dark:text-danger-300">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}
      <form onSubmit={handleSubmit} className="space-y-5">
        <Input label="Adresse e-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="vous@exemple.fr" required icon={<Mail className="w-4 h-4" />} />
        <Button type="submit" className="w-full" size="lg" disabled={loading || !email.trim()}>
          {loading ? (<><Spinner className="w-4 h-4" /> Envoi...</>) : 'Envoyer le lien'}
        </Button>
      </form>
    </AuthLayout>
  );
}
