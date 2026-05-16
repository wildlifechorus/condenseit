import { Link, useLocation } from 'wouter';
import { JobBanner } from './JobBanner';

interface NavLink {
  href: string;
  label: string;
}

interface HeaderProps {
  onMobileMenuToggle?: () => void;
  mobileMenuOpen?: boolean;
}

const NAV_LINKS: NavLink[] = [
  { href: '/', label: 'Digest' },
  { href: '/admin', label: 'Admin' },
];

/** Sticky top header with brand, nav links, and digest job banner. */
export function Header({ onMobileMenuToggle, mobileMenuOpen = false }: HeaderProps) {
  const [location] = useLocation();

  return (
    <div class="sticky top-0 z-40">
      <header class="h-14 flex items-center justify-between gap-3 px-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700 shadow-sm">
        {/* Left: hamburger (mobile) + brand */}
        <div class="flex items-center gap-3">
          <button
            type="button"
            class="lg:hidden p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            onClick={onMobileMenuToggle}
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              {mobileMenuOpen ? (
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>

          <Link
            href="/"
            class="flex items-center gap-2 font-bold text-slate-900 dark:text-slate-100 hover:text-teal-600 dark:hover:text-teal-400 transition-colors no-underline"
          >
            <BrandMark />
            <span class="hidden sm:inline">CondenseIt</span>
          </Link>
        </div>

        {/* Right: nav + job banner */}
        <div class="flex items-center gap-1">
          <nav class="hidden lg:flex items-center mr-2">
            {NAV_LINKS.map(({ href, label }) => {
              const active =
                href === '/'
                  ? location === '/'
                  : location.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  class={[
                    'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors no-underline',
                    active
                      ? 'text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-900/20'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800',
                  ].join(' ')}
                >
                  {label}
                </Link>
              );
            })}
          </nav>

          <JobBanner />
        </div>
      </header>
    </div>
  );
}

function BrandMark() {
  return (
    <span
      class="w-7 h-7 rounded-lg flex-shrink-0 flex items-center justify-center text-white font-black text-xs"
      style="background: linear-gradient(135deg, #0d9488, #6366f1)"
    >
      C
    </span>
  );
}
