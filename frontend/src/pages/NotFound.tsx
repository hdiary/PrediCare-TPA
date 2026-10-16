import { Link } from 'react-router-dom';
import { Home, Compass } from 'lucide-react';
import { Logo } from '@/components/Logo';

export function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-50 dark:bg-surface-900 px-4">
      <div className="text-center max-w-md">
        <div className="mb-8 flex justify-center"><Logo size="lg" /></div>
        <div className="w-20 h-20 rounded-2xl bg-surface-100 dark:bg-surface-700 flex items-center justify-center mx-auto mb-6">
          <Compass className="w-10 h-10 text-surface-300 dark:text-surface-500" />
        </div>
        <h1 className="text-3xl font-bold text-surface-800 dark:text-surface-100 mb-2">404</h1>
        <p className="text-sm text-surface-500 dark:text-surface-400 mb-6">
          La page que vous recherchez n'existe pas ou a été déplacée.
        </p>
        <Link
          to="/"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-primary-700 hover:bg-primary-800 text-white font-medium text-sm transition-all"
        >
          <Home className="w-4 h-4" /> Retour à l'accueil
        </Link>
      </div>
    </div>
  );
}
