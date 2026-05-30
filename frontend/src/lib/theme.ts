export type Theme = 'dark' | 'light';

const DEFAULT_THEME: Theme = 'dark';
const THEME_STORAGE_KEY = 'condenseit:theme';

/** Check that a persisted value is one of the supported themes. */
function isTheme(value: string | null): value is Theme {
  return value === 'dark' || value === 'light';
}

/** Read the saved theme, falling back to dark mode by default. */
export function getInitialTheme(): Theme {
  if (typeof window === 'undefined') {
    return DEFAULT_THEME;
  }

  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);

    if (isTheme(storedTheme)) {
      return storedTheme;
    }
  } catch {
    return DEFAULT_THEME;
  }

  return DEFAULT_THEME;
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;

  root.classList.toggle('dark', theme === 'dark');
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
}

/** Persist and apply the selected theme. */
export function persistTheme(theme: Theme): void {
  applyTheme(theme);

  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Keep the in-memory theme if browser storage is unavailable.
  }
}
