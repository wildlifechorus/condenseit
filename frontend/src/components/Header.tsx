import { Link, useLocation } from 'wouter';
import { JobBanner } from './JobBanner';

interface NavLink {
  href: string;
  label: string;
}

interface HeaderProps {
  isPwa?: boolean;
  pwaTitle?: string;
  pwaDate?: string;
  onMobileMenuToggle?: () => void;
  mobileMenuOpen?: boolean;
}

const NAV_LINKS: NavLink[] = [
  { href: '/', label: 'Digest' },
  { href: '/admin', label: 'Admin' },
];

/**
 * Sticky top header.
 * In normal mode: shows brand, nav, and "Run digest" button + job banner.
 * In PWA mode: shows brand and digest timestamp only.
 */
export function Header({
  isPwa = false,
  pwaTitle,
  pwaDate,
  onMobileMenuToggle,
  mobileMenuOpen = false,
}: HeaderProps) {
  const [location] = useLocation();

  return (
    <div class="sticky top-0 z-40">
      {/* Main header bar */}
      <header class="h-14 flex items-center justify-between gap-3 px-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700 shadow-sm">
        {/* Left: hamburger (mobile) + brand */}
        <div class="flex items-center gap-3">
          {!isPwa && (
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
          )}

          {isPwa ? (
            <div class="flex items-center gap-2 select-none">
              <BrandMark />
              <div>
                <span class="font-bold text-slate-900 dark:text-slate-100 text-sm leading-none">
                  {pwaTitle ?? 'CondenseIt Digest'}
                </span>
                {pwaDate && (
                  <p class="text-xs text-slate-500 dark:text-slate-400 leading-tight">
                    {pwaDate}
                  </p>
                )}
              </div>
            </div>
          ) : (
            <Link
              href="/"
              class="flex items-center gap-2 font-bold text-slate-900 dark:text-slate-100 hover:text-teal-600 dark:hover:text-teal-400 transition-colors no-underline"
            >
              <BrandMark />
              <span class="hidden sm:inline">CondenseIt</span>
            </Link>
          )}
        </div>

        {/* Right: refresh button (PWA only) or nav + job banner (normal) */}
        {isPwa ? (
          <button
            type="button"
            onClick={() => window.location.reload()}
            aria-label="Refresh"
            title="Refresh digest"
            class="p-2 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-teal-600 dark:hover:text-teal-400 transition-colors"
          >
            <svg
              class="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              stroke-width="2"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </button>
        ) : (
          <div class="flex items-center gap-1">
            {/* Desktop nav */}
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
        )}
      </header>

      {/* Job banner lives inside Header and renders below */}
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
