import { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { Mail, Lock, Activity, AlertCircle, Eye, EyeOff, ShieldCheck, BarChart3, UserCheck } from 'lucide-react';
import { useAuth, getRoleHome } from '@/lib/auth';
import { Logo } from '@/components/Logo';
import { Button, Input, Spinner } from '@/components/ui';
import { MOCK_ACCOUNTS } from '@/lib/mockData';
import { USE_MOCK_AUTH } from '@/lib/api';
import { isMock } from '@/lib/api';

// Comptes créés par le backend quand DEMO_PASSWORD est défini (mot de passe : celui du .env)
const REAL_DEMO_ACCOUNTS = [
  { email: 'gestionnaire@predicare.local', display_name: 'Gestionnaire', pseudonym: 'Alertes et décisions' },
  { email: 'pro@predicare.local', display_name: 'Professionnel de santé', pseudonym: 'Dépôt de factures' },
  { email: 'assure@predicare.local', display_name: 'Assuré', pseudonym: 'Remboursements' },
  { email: 'admin@predicare.local', display_name: 'Administrateur', pseudonym: 'Configuration' },
];
const SHOW_DEMO = isMock('auth') || import.meta.env.VITE_SHOW_DEMO_ACCOUNTS === 'true';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // AppLayout transmet l'objet « location » de la page demandée (ou une chaîne) : on garde le chemin.
  const rawFrom = (location.state as { from?: string | { pathname?: string; search?: string } })?.from;
  const from = typeof rawFrom === 'string' ? rawFrom : rawFrom?.pathname ? rawFrom.pathname + (rawFrom.search ?? '') : undefined;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const loggedIn = await login(email, password);
      // La page demandée n'est reprise que si elle appartient au rôle connecté.
      const home = getRoleHome(loggedIn.role);
      navigate(from && from.startsWith(home) ? from : home);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur de connexion');
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = (accountEmail: string, accountPassword: string) => {
    setEmail(accountEmail);
    setPassword(accountPassword);
    setError('');
  };

  return (
    <div className="min-h-screen flex">
      {/* Left panel */}
      <div className="hidden lg:block lg:w-1/2 gradient-hero relative overflow-hidden px-20 pt-[140px] pb-[60px]">
        <div className="absolute -top-[120px] -right-20 w-[420px] h-[420px] rounded-full bg-[#7C9A98] opacity-35" />
        <div className="absolute top-[86px] right-10 w-[290px] h-[290px] rounded-full border border-[#8FB5B1]" />
        <div className="absolute top-[150px] right-[130px] w-[290px] h-[290px] rounded-full border border-[#5E7F7C]" />

        <div className="relative">
          <Logo size="lg" />
        </div>

        <h1 className="relative mt-12 text-[38px] leading-[1.2] text-surface-900 dark:text-[#E8F1F0]">
          Détecter la fraude.<br />
          Expliquer chaque alerte.<br />
          <span className="text-primary-700 dark:text-primary-400">Protéger les assurés.</span>
        </h1>

        <p className="relative mt-7 text-base leading-[1.6] text-surface-700 dark:text-surface-300">
          La plateforme intelligente pour les tiers-payants santé.<br />
          Analyse prédictive, explicabilité et contrôle humain.
        </p>

        <div className="relative flex flex-wrap gap-3 mt-9">
          {[
            { label: 'Conforme RGPD', icon: <ShieldCheck className="w-4 h-4" /> },
            { label: 'IA explicable', icon: <BarChart3 className="w-4 h-4" /> },
            { label: 'Contrôle humain', icon: <UserCheck className="w-4 h-4" /> },
          ].map((badge) => (
            <div key={badge.label} className="flex items-center gap-3 px-[18px] py-4 rounded-xl bg-white dark:bg-surface-800 border border-surface-300 dark:border-surface-700 text-sm font-semibold text-surface-900 dark:text-[#E8F1F0]">
              <span className="text-primary-700 dark:text-primary-400">{badge.icon}</span>
              {badge.label}
            </div>
          ))}
        </div>

        <div className="relative mt-10 w-80 p-[18px] rounded-xl bg-white dark:bg-surface-800 border border-surface-300 dark:border-surface-700">
          <div className="flex items-center gap-3 text-[13px] text-surface-500 dark:text-surface-400">
            <span className="w-8 h-8 rounded-lg bg-primary-50 text-primary-600 flex items-center justify-center">
              <Activity className="w-[18px] h-[18px]" />
            </span>
            Surveillance en continu
          </div>
          <svg viewBox="0 0 230 60" className="mt-3.5 w-[230px] h-[60px]" fill="none" aria-hidden="true">
            <path d="M0 34h50l14-24 18 46 14-22h28l14-20 16 40 12-20h64" stroke="#D9622B" strokeWidth="2" />
          </svg>
        </div>
      </div>

      {/* Right panel - login form */}
      <div className="flex-1 flex items-center justify-center px-6 py-10 dark:bg-[#1C2120]">
        <div className="w-full max-w-[448px] flex flex-col gap-6">
          <div className="lg:hidden mb-8 flex justify-center">
            <Logo size="lg" />
          </div>

          <div className="glass rounded-2xl p-8">
            <h2 className="text-[26px] text-surface-900 dark:text-[#E8F1F0]">Connexion</h2>
            <p className="mt-2 mb-6 text-sm text-surface-500 dark:text-surface-400">Accédez à votre espace PrediCare TPA</p>

            {error && (
              <div className="mb-4 flex items-start gap-2 p-3 rounded-2xl bg-danger-50 dark:bg-danger-900/30 border border-danger-200 dark:border-danger-800 text-sm text-danger-700 dark:text-danger-300">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <Input
                label="Adresse email"
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="vous@exemple.fr"
                required
                icon={<Mail className="w-4 h-4" />}
              />
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-200 mb-2">
                  Mot de passe <span className="text-danger-500">*</span>
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="w-full h-11 rounded-xl border border-surface-300 dark:border-surface-700 bg-white dark:bg-surface-900 text-surface-900 dark:text-[#E8F1F0] placeholder-surface-400 pl-10 pr-10 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="flex justify-end !mt-4">
                {USE_MOCK_AUTH ? (
                  <Link to="/mot-de-passe-oublie" className="text-sm text-primary-700 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 underline">Mot de passe oublié ?</Link>
                ) : (
                  <span className="text-sm text-surface-500 dark:text-surface-400">Pour réinitialiser votre accès, contactez un administrateur.</span>
                )}
              </div>

              <Button type="submit" className="w-full" size="lg" disabled={loading}>
                {loading ? (
                  <>
                    <Spinner className="w-4 h-4" /> Connexion...
                  </>
                ) : (
                  'Se connecter'
                )}
              </Button>
            </form>

            <p className="mt-6 text-center text-sm text-surface-500 dark:text-surface-400">
              {USE_MOCK_AUTH ? (
                <>
                  Pas encore de compte ?{' '}
                  <Link to="/inscription" className="text-primary-700 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 underline">Créer un compte</Link>
                </>
              ) : (
                "La création de compte est gérée par un administrateur."
              )}
            </p>
          </div>

          {/* Comptes de démonstration (mode simulé, ou VITE_SHOW_DEMO_ACCOUNTS=true) */}
          {SHOW_DEMO && (
            <div className="glass rounded-2xl px-5 pt-5 pb-[22px]">
              <p className="text-xs text-surface-500 dark:text-surface-400 mb-3.5 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#4ADE80]" />
                Comptes de démonstration
              </p>
              <div className="grid grid-cols-2 gap-2">
                {(isMock('auth') ? MOCK_ACCOUNTS : REAL_DEMO_ACCOUNTS.map((a) => ({ ...a, role: a.email, password: '' }))).map((acc) => (
                  <button
                    key={acc.role}
                    type="button"
                    onClick={() => fillDemo(acc.email, acc.password)}
                    className="text-left px-3.5 py-3 rounded-xl border border-surface-300 dark:border-[#2A6A6B] bg-white hover:bg-surface-100 dark:bg-[#12363A] dark:hover:bg-surface-700 transition-colors"
                  >
                    <p className="text-[13px] font-semibold text-surface-900 dark:text-[#E8F1F0]">{acc.display_name}</p>
                    <p className="text-[11px] text-surface-500 dark:text-surface-400 mt-1">{acc.pseudonym}</p>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
