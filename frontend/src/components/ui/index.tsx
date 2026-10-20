import { type ReactNode } from 'react';

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl glass ${className}`}>
      {children}
    </div>
  );
}

export function Badge({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium ${className}`}>
      {children}
    </span>
  );
}

export function Button({
  children,
  onClick,
  variant = 'primary',
  size = 'md',
  className = '',
  disabled = false,
  type = 'button',
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  disabled?: boolean;
  type?: 'button' | 'submit';
}) {
  const variants = {
    primary: 'bg-primary-600 hover:bg-primary-700 text-white shadow-soft',
    secondary: 'bg-surface-200 hover:bg-surface-300/70 text-surface-900 dark:bg-surface-700 dark:hover:bg-surface-600 dark:text-surface-50',
    outline: 'bg-white dark:bg-surface-800 border border-surface-300 dark:border-surface-600 hover:bg-surface-100 dark:hover:bg-surface-700 text-surface-800 dark:text-surface-100',
    ghost: 'hover:bg-surface-200/70 dark:hover:bg-surface-700 text-surface-700 dark:text-surface-200',
    danger: 'bg-danger-600 hover:bg-danger-700 text-white shadow-soft',
  };
  const sizes = {
    sm: 'h-9 px-4 text-sm',
    md: 'h-11 px-5 text-sm',
    lg: 'h-12 px-6 text-base',
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-colors active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {children}
    </button>
  );
}

export function Input({
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
  error,
  required = false,
  icon,
  id,
  pattern,
  maxLength,
}: {
  label?: string;
  type?: string;
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  error?: string;
  required?: boolean;
  icon?: ReactNode;
  id?: string;
  pattern?: string;
  maxLength?: number;
}) {
  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-surface-700 dark:text-surface-200 mb-2">
          {label} {required && <span className="text-danger-500">*</span>}
        </label>
      )}
      <div className="relative">
        {icon && <div className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400">{icon}</div>}
        <input
          id={id}
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          required={required}
          pattern={pattern}
          maxLength={maxLength}
          className={`w-full rounded-xl border bg-white dark:bg-surface-900 text-surface-900 dark:text-surface-100 placeholder-surface-400 dark:placeholder-surface-500 h-11 px-3.5 text-sm ${icon ? 'pl-10' : ''} ${error ? 'border-danger-400' : 'border-surface-300 dark:border-surface-600'} focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20`}
        />
      </div>
      {error && <p className="mt-1 text-xs text-danger-500">{error}</p>}
    </div>
  );
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function EmptyState({ icon, title, description, action }: { icon: ReactNode; title: string; description: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-16 h-16 rounded-2xl bg-surface-200 dark:bg-surface-700 flex items-center justify-center text-surface-500 mb-4">
        {icon}
      </div>
      <h3 className="text-lg font-semibold text-surface-700 dark:text-surface-200 mb-1">{title}</h3>
      <p className="text-sm text-surface-500 dark:text-surface-400 max-w-sm mb-4">{description}</p>
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-16 h-16 rounded-2xl bg-danger-50 dark:bg-danger-900/30 flex items-center justify-center text-danger-500 mb-4">
        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <p className="text-sm text-surface-600 dark:text-surface-400 mb-4">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>Réessayer</Button>
      )}
    </div>
  );
}

export function Spinner({ className = '' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  );
}

export function Drawer({ open, onClose, title, children, width = 'md' }: { open: boolean; onClose: () => void; title: string; children: ReactNode; width?: 'sm' | 'md' | 'lg' }) {
  if (!open) return null;
  const widths = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-2xl' };
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-surface-900/40 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div className={`relative w-full ${widths[width]} bg-white dark:bg-surface-800 shadow-lg border-l border-surface-300/80 dark:border-surface-700 overflow-y-auto animate-slide-in-right`}>
        <div className="sticky top-0 z-10 flex items-center justify-between px-5 md:px-8 py-5 border-b border-surface-300/80 dark:border-surface-700 bg-white dark:bg-surface-800">
          <h2 className="text-lg font-medium text-surface-900 dark:text-surface-100">{title}</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-200/70 dark:hover:bg-surface-700 text-surface-500">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-5 md:p-8">{children}</div>
      </div>
    </div>
  );
}

export function Modal({ open, onClose, title, children, footer }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-surface-900/40 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div className="relative w-full max-w-md bg-white dark:bg-surface-800 rounded-2xl border border-surface-300/80 dark:border-surface-700 shadow-lg animate-slide-up">
        <div className="px-8 py-5 border-b border-surface-300/80 dark:border-surface-700">
          <h2 className="text-lg font-medium text-surface-900 dark:text-surface-100">{title}</h2>
        </div>
        <div className="p-8">{children}</div>
        {footer && (
          <div className="px-8 py-5 border-t border-surface-300/80 dark:border-surface-700 flex justify-end gap-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

export function StatusPill({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium border ${className}`}>
      {label}
    </span>
  );
}
