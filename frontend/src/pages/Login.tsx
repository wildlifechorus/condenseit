import { useState } from 'preact/hooks';

import type { JSX } from 'preact';

import { ThemeToggle } from '../components/ThemeToggle';
import { login } from '../lib/auth';

interface LoginPageProps {
  /** Called when the user successfully authenticates. */
  onLogin: () => void;
}

/**
 * Full-screen login form shown when the session cookie is absent or expired.
 * Submits a password to POST /api/auth/login and calls onLogin on success.
 */
export function LoginPage({ onLogin }: LoginPageProps) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  /** Handle form submit: send password to the API. */
  async function handleSubmit(e: JSX.TargetedEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!password.trim()) {
      return;
    }
    setLoading(true);
    setError(null);

    const err = await login(password);

    setLoading(false);

    if (err) {
      setError(err);
      setPassword('');
    } else {
      onLogin();
    }
  }

  return (
    <div
      class={[
        'relative min-h-screen flex flex-col items-center justify-center',
        'bg-slate-50 dark:bg-slate-950 px-4',
      ].join(' ')}
    >
      <div class='absolute right-4 top-4'>
        <ThemeToggle />
      </div>

      {/* Card */}
      <div class='w-full max-w-sm bg-white dark:bg-slate-900 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-8'>
        {/* Brand */}
        <div class='flex flex-col items-center gap-3 mb-8'>
          <span
            class='w-12 h-12 rounded-xl flex items-center justify-center text-white font-black text-lg select-none'
            style='background: linear-gradient(135deg, #0d9488, #6366f1)'
          >
            C
          </span>
          <div class='text-center'>
            <h1 class='text-lg font-bold text-slate-900 dark:text-slate-100 leading-tight'>
              CondenseIt
            </h1>
            <p class='text-sm text-slate-500 dark:text-slate-400'>
              Sign in to your digest
            </p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} class='flex flex-col gap-4'>
          <div class='flex flex-col gap-1.5'>
            <label
              for='password'
              class='text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide'
            >
              Password
            </label>
            <input
              id='password'
              type='password'
              autoComplete='current-password'
              required
              value={password}
              onInput={(e) =>
                setPassword((e.target as HTMLInputElement).value)
              }
              placeholder='Enter your password'
              class={[
                'w-full px-3 py-2.5 rounded-lg text-sm border outline-none',
                'bg-white dark:bg-slate-800',
                'text-slate-900 dark:text-slate-100',
                'placeholder-slate-400 dark:placeholder-slate-500',
                'transition-colors',
                error
                  ? 'border-red-400 dark:border-red-500 focus:border-red-500 dark:focus:border-red-400'
                  : 'border-slate-300 dark:border-slate-600 focus:border-teal-500 dark:focus:border-teal-400',
              ].join(' ')}
            />
          </div>

          {/* Error message */}
          {error && (
            <p
              role='alert'
              class='text-sm text-red-600 dark:text-red-400 -mt-1'
            >
              {error}
            </p>
          )}

          <button
            type='submit'
            disabled={loading || !password.trim()}
            class={[
              'w-full py-2.5 rounded-lg text-sm font-semibold text-white',
              'bg-teal-600 hover:bg-teal-700 dark:bg-teal-500 dark:hover:bg-teal-600',
              'transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'flex items-center justify-center gap-2',
            ].join(' ')}
          >
            {loading && (
              <span class='w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin' />
            )}
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}
