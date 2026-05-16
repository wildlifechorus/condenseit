type BadgeVariant =
  | 'article'
  | 'video'
  | 'watch'
  | 'rss'
  | 'youtube'
  | 'website'
  | 'ok'
  | 'error'
  | 'default';

interface BadgeProps {
  variant?: BadgeVariant;
  children: string;
  className?: string;
}

const COLORS: Record<BadgeVariant, string> = {
  article:
    'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300',
  video:
    'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300',
  watch:
    'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300',
  rss:
    'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
  youtube:
    'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300',
  website:
    'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300',
  ok:
    'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300',
  error:
    'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300',
  default:
    'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400',
};

/** Determines badge variant from a string value. */
export function kindVariant(kind: string): BadgeVariant {
  const k = kind.toLowerCase();
  if (k === 'article') return 'article';
  if (k === 'video') return 'video';
  if (k === 'watch') return 'watch';
  if (k === 'rss') return 'rss';
  if (k === 'youtube') return 'youtube';
  if (k === 'website') return 'website';
  if (k === 'ok') return 'ok';
  if (k === 'error' || k === 'err') return 'error';
  return 'default';
}

/** Small label badge with color variants. */
export function Badge({ variant = 'default', children, className = '' }: BadgeProps) {
  return (
    <span
      class={[
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wide',
        COLORS[variant],
        className,
      ].join(' ')}
    >
      {children}
    </span>
  );
}
