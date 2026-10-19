import { Logo } from './Logo';

/** Animation de chargement : logo qui pulse et barre de progression indéterminée.
 *  `fullscreen` pour l'écran entier, sinon elle remplit la zone de contenu. */
export function PageLoader({ fullscreen = false, label = 'Chargement…' }: { fullscreen?: boolean; label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex flex-col items-center justify-center gap-5 ${fullscreen ? 'min-h-screen' : 'min-h-[50vh]'}`}
    >
      <div className="animate-pulse-soft motion-reduce:animate-none">
        <Logo size="lg" />
      </div>
      <div className="h-1 w-40 rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
        <div className="h-full w-2/5 motion-reduce:w-full rounded-full bg-primary-600 animate-loader-bar motion-reduce:animate-none" />
      </div>
      <span className="sr-only">{label}</span>
    </div>
  );
}
