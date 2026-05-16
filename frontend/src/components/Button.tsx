import type { ComponentChildren, JSX } from 'preact';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md';

interface ButtonProps {
  variant?: Variant;
  size?: Size;
  disabled?: boolean;
  loading?: boolean;
  type?: 'button' | 'submit' | 'reset';
  onClick?: JSX.MouseEventHandler<HTMLButtonElement>;
  children: ComponentChildren;
  className?: string;
  title?: string;
}

const VARIANT: Record<Variant, string> = {
  primary:
    'bg-teal-600 text-white hover:bg-teal-700 dark:bg-teal-500 dark:hover:bg-teal-600',
  secondary:
    'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-600 hover:bg-slate-200 dark:hover:bg-slate-700',
  ghost:
    'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800',
  danger:
    'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/40',
};

const SIZE: Record<Size, string> = {
  sm: 'px-2.5 py-1.5 text-xs rounded-md gap-1',
  md: 'px-4 py-2 text-sm rounded-lg gap-1.5',
};

/** Reusable button with variant + size system. */
export function Button({
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  type = 'button',
  onClick,
  children,
  className = '',
  title,
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      title={title}
      class={[
        'inline-flex items-center justify-center font-semibold cursor-pointer',
        'transition-colors select-none disabled:opacity-50 disabled:cursor-not-allowed',
        VARIANT[variant],
        SIZE[size],
        className,
      ].join(' ')}
    >
      {loading && (
        <span
          class={`inline-block rounded-full border-current border-t-transparent animate-spin ${
            size === 'sm' ? 'w-3 h-3 border-[1.5px]' : 'w-3.5 h-3.5 border-2'
          }`}
        />
      )}
      {children}
    </button>
  );
}
