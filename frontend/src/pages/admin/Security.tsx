import { useState, useEffect } from 'preact/hooks';
import { api } from '../../lib/api';
import type { PasswordInfo } from '../../lib/types';
import { Card, CardHeader } from '../../components/Card';
import { Button } from '../../components/Button';
import { Spinner } from '../../components/Spinner';

const INPUT =
  'w-full px-3 py-2 text-sm bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500';

export function SecurityPage() {
  const [info, setInfo] = useState<PasswordInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState<{ text: string; ok: boolean } | null>(
    null,
  );

  useEffect(() => {
    api
      .getPasswordInfo()
      .then(setInfo)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function showFlash(text: string, ok = true) {
    setFlash({ text, ok });
    setTimeout(() => setFlash(null), 5000);
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (next !== confirm) {
      showFlash('New passwords do not match.', false);
      return;
    }
    if (next.length < 8) {
      showFlash('New password must be at least 8 characters.', false);
      return;
    }
    setSaving(true);
    try {
      await api.changePassword(current, next);
      setCurrent('');
      setNext('');
      setConfirm('');
      setInfo((prev) => (prev ? { ...prev, source: 'db', using_default: false } : prev));
      showFlash('Password changed. You will be asked to log in again on your next session.');
    } catch (err) {
      showFlash(
        err instanceof Error ? err.message : 'Failed to change password.',
        false,
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div class="flex items-center justify-center py-20">
        <Spinner size="lg" className="text-teal-600 dark:text-teal-400" />
      </div>
    );
  }

  return (
    <div class="space-y-5">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Security
        </h1>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Manage your admin password.
        </p>
      </div>

      {/* Default password warning */}
      {info?.using_default && (
        <div class="flex items-start gap-3 px-4 py-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 text-sm text-amber-800 dark:text-amber-300">
          <svg
            class="w-5 h-5 flex-shrink-0 mt-0.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="2"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
            />
          </svg>
          <div>
            <p class="font-semibold">You are using the default password.</p>
            <p class="mt-0.5 text-xs opacity-80">
              Change it below before exposing this instance to the internet.
            </p>
          </div>
        </div>
      )}

      {flash && (
        <div
          class={[
            'px-4 py-3 text-sm rounded-lg border',
            flash.ok
              ? 'bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-800'
              : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800',
          ].join(' ')}
        >
          {flash.text}
        </div>
      )}

      <Card>
        <CardHeader
          title="Change password"
          description="Changes take effect immediately. Your current session stays active."
        />
        <form onSubmit={handleSubmit} class="space-y-4">
          <label class="flex flex-col gap-1">
            <span class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Current password
            </span>
            <input
              type="password"
              class={INPUT}
              required
              autoComplete="current-password"
              value={current}
              onInput={(e) => setCurrent((e.target as HTMLInputElement).value)}
            />
          </label>

          <label class="flex flex-col gap-1">
            <span class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              New password
            </span>
            <input
              type="password"
              class={INPUT}
              required
              minLength={8}
              autoComplete="new-password"
              value={next}
              onInput={(e) => setNext((e.target as HTMLInputElement).value)}
            />
            <span class="text-xs text-slate-400 dark:text-slate-500">
              Minimum 8 characters.
            </span>
          </label>

          <label class="flex flex-col gap-1">
            <span class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Confirm new password
            </span>
            <input
              type="password"
              class={INPUT}
              required
              autoComplete="new-password"
              value={confirm}
              onInput={(e) => setConfirm((e.target as HTMLInputElement).value)}
            />
          </label>

          <div class="pt-1">
            <Button type="submit" loading={saving}>
              Change password
            </Button>
          </div>
        </form>
      </Card>

      {info && !info.using_default && (
        <Card>
          <p class="text-xs text-slate-400 dark:text-slate-500">
            Password source:{' '}
            <code class="bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">
              {info.source === 'db'
                ? 'set via admin panel'
                : info.source === 'env'
                  ? 'CONDENSEIT_AUTH_PASSWORD env var'
                  : 'built-in default'}
            </code>
            {'. '}
            Passwords set via admin panel take priority over the env var.
          </p>
        </Card>
      )}
    </div>
  );
}
