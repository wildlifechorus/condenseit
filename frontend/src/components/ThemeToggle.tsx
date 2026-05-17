import { useState } from 'preact/hooks';

import {
  getInitialTheme,
  persistTheme,
  type Theme,
} from '../lib/theme';

const SUN_ICON_PATH = [
  'M12 3v2.25',
  'M18.364 5.636l-1.591 1.591',
  'M21 12h-2.25',
  'M18.364 18.364l-1.591-1.591',
  'M12 18.75V21',
  'M7.227 16.773l-1.591 1.591',
  'M5.25 12H3',
  'M7.227 7.227 5.636 5.636',
  'M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z',
].join(' ');

const MOON_ICON_PATH = [
  'M21.752 15.002A9.718 9.718 0 0118 15.75',
  '9.75 9.75 0 018.25 6c0-1.33.266-2.597.748-3.752',
  'A9.753 9.753 0 003 11.25 9.75 9.75 0 0012.75 21',
  'a9.753 9.753 0 009.002-5.998z',
].join(' ');

/** Toggle between the persisted light and dark UI themes. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => getInitialTheme());
  const isDark = theme === 'dark';
  const label = isDark ? 'Switch to light mode' : 'Switch to dark mode';

  /** Persist the next theme before updating the visible icon state. */
  function handleToggle() {
    setTheme((currentTheme) => {
      const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';

      persistTheme(nextTheme);

      return nextTheme;
    });
  }

  return (
    <button
      type="button"
      class={[
        'inline-flex h-9 w-9 flex-shrink-0 items-center justify-center',
        'rounded-lg border border-slate-300 bg-white text-slate-700',
        'shadow-sm transition-colors hover:bg-slate-100',
        'dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300',
        'dark:hover:bg-slate-800',
      ].join(' ')}
      onClick={handleToggle}
      title={label}
      aria-label={label}
      aria-pressed={isDark}
    >
      {isDark ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

/** Sun icon shown while dark mode is active. */
function SunIcon() {
  return (
    <svg
      class="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      stroke-width="2"
      aria-hidden="true"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d={SUN_ICON_PATH}
      />
    </svg>
  );
}

/** Moon icon shown while light mode is active. */
function MoonIcon() {
  return (
    <svg
      class="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      stroke-width="2"
      aria-hidden="true"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d={MOON_ICON_PATH}
      />
    </svg>
  );
}
