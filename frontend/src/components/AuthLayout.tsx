import type { ReactNode } from 'react';
import { Logo } from './Logo';

/** Cadre commun aux pages publiques (inscription, mot de passe oublié, réinitialisation). */
export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10 dark:bg-[#1C2120]">
      <div className="w-full max-w-[480px] flex flex-col gap-6 animate-page-in motion-reduce:animate-none">
        <div className="flex justify-center">
          <Logo size="lg" />
        </div>
        <div className="glass rounded-2xl p-6 md:p-8">
          <h2 className="text-[26px] text-surface-900 dark:text-[#E8F1F0]">{title}</h2>
          {subtitle && <p className="mt-2 mb-6 text-sm text-surface-500 dark:text-surface-400">{subtitle}</p>}
          {children}
        </div>
        {footer && <div className="text-center text-sm text-surface-500 dark:text-surface-400">{footer}</div>}
      </div>
    </div>
  );
}
