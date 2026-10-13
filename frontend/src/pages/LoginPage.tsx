import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Mail, Lock, Activity, AlertCircle, Eye, EyeOff, ShieldCheck, BarChart3, UserCheck } from 'lucide-react';
import { useAuth, getRoleHome } from '@/lib/auth';
import { Logo } from '@/components/Logo';
import { Button, Input, Spinner } from '@/components/ui';
import { MOCK_ACCOUNTS } from '@/lib/mockData';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const from = (location.state as { from?: string })?.from;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      const token = localStorage.getItem('predicare_token');
      const account = MOCK_ACCOUNTS.find((a) => 'mock-jwt-' + a.role === token);
      if (account) {
        if (from && from.startsWith('/')) {
          navigate(from);
        } else {
          navigate(getRoleHome(account.role));
        }
      }
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
      <div className="hidden lg:flex lg:w-1/2 gradient-hero relative overflow-hidden">
        <div className="absolute -top-24 -right-24 w-[28rem] h-[28rem] rounded-full bg-primary-100/70 blur-3xl" />
        <div className="absolute -bottom-24 -left-16 w-80 h-80 rounded-full bg-kraft-200/50 blur-3xl" />
        <div className="absolute right-10 top-24 w-72 h-72 rounded-full border border-primary-200/70" />
        <div className="absolute right-24 top-40 w-72 h-72 rounded-full border border-primary-200/40" />

        <div className="relative flex flex-col justify-center px-12 xl:px-20 w-full">
          <div className="mb-10">
            <Logo size="lg" />
          </div>

          <h1 className="text-3xl xl:text-4xl font-semibold leading-[1.2] mb-5 max-w-lg text-surface-900 dark:text-white tracking-tight">
            Détecter la fraude.<br />
            Expliquer chaque alerte.<br />
            <span className="text-primary-600 dark:text-primary-300">Protéger les assurés.</span>
          </h1>

          <p className="text-surface-600 dark:text-surface-300 text-base mb-10 max-w-md leading-relaxed">
            La plateforme intelligente pour les tiers-payants santé. Analyse prédictive, explicabilité et contrôle humain.
          </p>

          <div className="flex flex-wrap gap-3 max-w-lg mb-10">
            {[
              { label: 'Conforme RGPD', icon: <ShieldCheck className="w-4 h-4" /> },
              { label: 'IA explicable', icon: <BarChart3 className="w-4 h-4" /> },
              { label: 'Contrôle humain', icon: <UserCheck className="w-4 h-4" /> },
            ].map((badge) => (
              <div key={badge.label} className="float-chip flex items-center gap-2.5 pl-2.5 pr-4 py-2">
                <span className="w-8 h-8 rounded-lg bg-kraft-100 text-kraft-700 flex items-center justify-center">{badge.icon}</span>
                <span className="text-sm font-semibold text-surface-900 dark:text-white">{badge.label}</span>
              </div>
            ))}
          </div>

          {/* Carte flottante : ligne de suivi, façon tableau de bord médical */}
          <div className="float-chip p-4 max-w-xs">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-8 h-8 rounded-lg bg-primary-50 text-primary-700 flex items-center justify-center">
                <Activity className="w-4 h-4" />
              </span>
              <span className="text-xs font-semibold text-surface-500">Surveillance en continu</span>
            </div>
            <svg viewBox="0 0 240 60" className="w-full h-14" fill="none" aria-hidden="true">
              <path d="M0 34 H52 L64 14 L80 52 L94 24 L106 34 H150 L162 18 L176 46 L188 34 H240"
                stroke="#C15F3C" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>
      </div>

      {/* Right panel - login form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-8 flex justify-center">
            <Logo size="lg" />
          </div>

          <div className="glass rounded-2xl p-8">
            <h2 className="text-2xl font-semibold text-surface-900 dark:text-surface-100 mb-1">Connexion</h2>
            <p className="text-sm text-surface-500 dark:text-surface-400 mb-6">Accédez à votre espace PrediCare TPA</p>

            {error && (
              <div className="mb-4 flex items-start gap-2 p-3 rounded-2xl bg-danger-50 dark:bg-danger-900/30 border border-danger-200 dark:border-danger-800 text-sm text-danger-700 dark:text-danger-300">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="Adresse email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="vous@exemple.fr"
                required
                icon={<Mail className="w-4 h-4" />}
              />
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
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
                    className="w-full rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-900 text-surface-900 dark:text-surface-100 placeholder-surface-400 pl-10 pr-10 py-2.5 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-100"
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

              <div className="flex justify-end">
                <span className="text-sm text-primary-600 hover:text-primary-700 cursor-pointer">Mot de passe oublié ?</span>
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
          </div>

          {/* Demo accounts */}
          <div className="mt-6 glass rounded-2xl p-5">
            <p className="text-xs font-medium text-surface-500 dark:text-surface-400 mb-3 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-success-500 animate-pulse" />
              Comptes de démonstration
            </p>
            <div className="grid grid-cols-2 gap-2">
              {MOCK_ACCOUNTS.map((acc) => (
                <button
                  key={acc.role}
                  onClick={() => fillDemo(acc.email, acc.password)}
                  className="text-left px-4 py-3 rounded-xl border border-surface-300/80 bg-white hover:bg-surface-100 dark:bg-surface-700/50 dark:hover:bg-primary-900/20 transition-all"
                >
                  <p className="text-xs font-medium text-surface-700 dark:text-surface-200">{acc.display_name}</p>
                  <p className="text-[10px] text-surface-400 mt-0.5">{acc.pseudonym}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
