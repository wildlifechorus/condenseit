type BadgeVariant =
  | 'article'
  | 'video'
  | 'watch'
  | 'rss'
  | 'youtube'
  | 'website'
  | 'google_news'
  | 'hackernews'
  | 'reddit'
  | 'github_releases'
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
  google_news:
    'bg-sky-50 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300',
  hackernews:
    'bg-orange-50 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300',
  reddit:
    'bg-orange-100 dark:bg-orange-900/40 text-orange-800 dark:text-orange-200',
  github_releases:
    'bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300',
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
  if (k === 'google_news') return 'google_news';
  if (k === 'hackernews') return 'hackernews';
  if (k === 'reddit') return 'reddit';
  if (k === 'github_releases') return 'github_releases';
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
