import { useState } from 'react';
import { Lock, Eye, EyeOff, Check, Circle } from 'lucide-react';
import type { PasswordCheck } from '@/lib/password';

export function PasswordField({
  label,
  value,
  onChange,
  autoComplete,
  id,
  error,
  placeholder = '••••••••••••',
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: 'new-password' | 'current-password';
  id: string;
  error?: string;
  placeholder?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-surface-700 dark:text-surface-200 mb-2">
        {label} <span className="text-danger-500">*</span>
      </label>
      <div className="relative">
        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
        <input
          id={id}
          type={show ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          placeholder={placeholder}
          required
          className="w-full h-11 rounded-xl border border-surface-300 dark:border-surface-700 bg-white dark:bg-surface-900 text-surface-900 dark:text-[#E8F1F0] placeholder-surface-400 pl-10 pr-10 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
        />
        <button
          type="button"
          onClick={() => setShow(!show)}
          aria-label={show ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600"
        >
          {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
      {error && <p className="mt-1.5 text-xs text-danger-600 dark:text-danger-300">{error}</p>}
    </div>
  );
}

/** Liste des règles, cochées au fur et à mesure de la saisie. */
export function PasswordRules({ checks, visible }: { checks: PasswordCheck[]; visible: boolean }) {
  if (!visible) return null;
  return (
    <ul className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1" aria-live="polite">
      {checks.map((c) => (
        <li
          key={c.label}
          className={`flex items-center gap-2 text-xs ${
            c.ok ? 'text-success-700 dark:text-success-300' : 'text-surface-500 dark:text-surface-400'
          }`}
        >
          {c.ok ? <Check className="w-3.5 h-3.5 shrink-0" /> : <Circle className="w-3.5 h-3.5 shrink-0" />}
          {c.label}
        </li>
      ))}
    </ul>
  );
}
