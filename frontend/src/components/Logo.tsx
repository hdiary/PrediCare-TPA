import { ShieldPlus } from 'lucide-react';

export function Logo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizes = {
    sm: { box: 'w-8 h-8', icon: 'w-5 h-5', text: 'text-base' },
    md: { box: 'w-9 h-9', icon: 'w-5 h-5', text: 'text-lg' },
    lg: { box: 'w-12 h-12', icon: 'w-[26px] h-[26px]', text: 'text-2xl' },
  };
  const s = sizes[size];
  return (
    <div className="flex items-center gap-2.5">
      <div className={`${s.box} rounded-[10px] bg-primary-600 flex items-center justify-center text-white`}>
        <ShieldPlus className={s.icon} />
      </div>
      <div className="leading-none">
        <span className={`${s.text} font-semibold text-surface-900 dark:text-[#E8F1F0] tracking-tight`}>PrediCare</span>
        <span className={`${s.text} font-medium text-primary-700 dark:text-primary-400 tracking-tight`}> TPA</span>
      </div>
    </div>
  );
}
