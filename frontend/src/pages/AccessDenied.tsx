import { Link } from 'react-router-dom';
import { ShieldX, ArrowLeft } from 'lucide-react';
import { Logo } from '@/components/Logo';
import { useAuth } from '@/lib/auth';
import { getRoleHome } from '@/lib/auth';

export function AccessDeniedPage() {
  const { user } = useAuth();
  const homeLink = user ? getRoleHome(user.role) : '/login';

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-50 dark:bg-surface-900 px-4">
      <div className="text-center max-w-md">
        <div className="mb-8 flex justify-center"><Logo size="lg" /></div>
        <div className="w-20 h-20 rounded-2xl bg-danger-50 dark:bg-danger-900/30 flex items-center justify-center mx-auto mb-6">
          <ShieldX className="w-10 h-10 text-danger-500" />
        </div>
        <h1 className="text-2xl font-bold text-surface-800 dark:text-surface-100 mb-2">Accès refusé</h1>
        <p className="text-sm text-surface-500 dark:text-surface-400 mb-6">
          Vous n'avez pas les autorisations nécessaires pour accéder à cette page.
        </p>
        <Link
          to={homeLink}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-primary-700 hover:bg-primary-800 text-white font-medium text-sm transition-all"
        >
          <ArrowLeft className="w-4 h-4" /> Retour à mon espace
        </Link>
      </div>
    </div>
  );
}
