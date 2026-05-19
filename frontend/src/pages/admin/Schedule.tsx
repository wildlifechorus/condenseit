import { useState, useEffect } from 'preact/hooks';
import { api } from '../../lib/api';
import type { ScheduleConfig } from '../../lib/types';
import { Card, CardHeader } from '../../components/Card';
import { Button } from '../../components/Button';
import { Spinner } from '../../components/Spinner';

const INPUT =
  'px-3 py-2 text-sm bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500';

const TIME_RE = /^([01]\d|2[0-3]):([0-5]\d)$/;

/** All IANA timezone names available in this browser, grouped by region. */
const TIMEZONE_GROUPS: Record<string, string[]> = (() => {
  let all: string[];
  try {
    all = (Intl as any).supportedValuesOf('timeZone') as string[];
  } catch {
    all = ['UTC'];
  }
  const groups: Record<string, string[]> = {};
  for (const tz of all) {
    const slash = tz.indexOf('/');
    const region = slash === -1 ? 'General' : tz.slice(0, slash);
    (groups[region] ??= []).push(tz);
  }
  return groups;
})();

const ALL_TIMEZONES = Object.values(TIMEZONE_GROUPS).flat();

/** Format a UTC ISO string in the given IANA timezone. */
function formatInTz(utcIso: string, tz: string): string {
  try {
    return new Date(utcIso).toLocaleString('en-GB', {
      timeZone: tz,
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  } catch {
    return utcIso;
  }
}

export function SchedulePage() {
  const [cfg, setCfg] = useState<ScheduleConfig | null>(null);
  const [times, setTimes] = useState<string[]>([]);
  const [enabled, setEnabled] = useState(false);
  const [timezone, setTimezone] = useState('UTC');
  const [loading, setLoading] = useState(true);
  const [savingTimes, setSavingTimes] = useState(false);
  const [togglingEnabled, setTogglingEnabled] = useState(false);
  const [flash, setFlash] = useState<{ text: string; ok: boolean } | null>(
    null,
  );

  useEffect(() => {
    api
      .getScheduleConfig()
      .then((c) => {
        setCfg(c);
        setTimes(c.times.length > 0 ? c.times : ['07:00']);
        setEnabled(c.enabled);
        setTimezone(c.timezone || 'UTC');
      })
      .catch((e: unknown) => {
        showFlash(
          e instanceof Error ? e.message : 'Failed to load schedule.',
          false,
        );
      })
      .finally(() => setLoading(false));
  }, []);

  function showFlash(text: string, ok = true) {
    setFlash({ text, ok });
    setTimeout(() => setFlash(null), 4000);
  }

  async function handleToggleEnabled() {
    setTogglingEnabled(true);
    const next = !enabled;
    try {
      await api.saveScheduleConfig({ enabled: next });
      setEnabled(next);
      setCfg((prev) => (prev ? { ...prev, enabled: next } : prev));
      showFlash(next ? 'Scheduler enabled.' : 'Scheduler disabled.');
    } catch (err) {
      showFlash(err instanceof Error ? err.message : 'Toggle failed.', false);
    } finally {
      setTogglingEnabled(false);
    }
  }

  function addTime() {
    setTimes((prev) => [...prev, '08:00']);
  }

  function removeTime(idx: number) {
    setTimes((prev) => prev.filter((_, i) => i !== idx));
  }

  function updateTime(idx: number, value: string) {
    setTimes((prev) => prev.map((t, i) => (i === idx ? value : t)));
  }

  async function handleSaveTimes(e: Event) {
    e.preventDefault();
    const invalid = times.filter((t) => !TIME_RE.test(t));
    if (invalid.length > 0) {
      showFlash(
        `Invalid time(s): ${invalid.join(', ')}. Use HH:MM format.`,
        false,
      );
      return;
    }
    setSavingTimes(true);
    try {
      await api.saveScheduleConfig({ times, timezone });
      setCfg((prev) => (prev ? { ...prev, times, timezone } : prev));
      showFlash('Schedule saved.');
    } catch (err) {
      showFlash(err instanceof Error ? err.message : 'Save failed.', false);
    } finally {
      setSavingTimes(false);
    }
  }

  /** Human-readable next-run string in the user's timezone. */
  function nextRunLabel(): string {
    if (!cfg?.next_run_utc) return '';
    const utc = cfg.next_run_utc.replace('T', ' ').replace('Z', ' UTC');
    if (timezone === 'UTC') return utc;
    const local = formatInTz(cfg.next_run_utc, timezone);
    return `${local} (${timezone}) · ${utc}`;
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
          Schedule
        </h1>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Enable automatic digest runs and set the times they fire each day.
        </p>
      </div>

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

      {/* Enable / disable toggle */}
      <Card>
        <div class="flex items-center justify-between gap-4">
          <div>
            <p class="text-sm font-semibold text-slate-800 dark:text-slate-200">
              Automatic scheduling
            </p>
            <p class="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
              {enabled
                ? cfg?.next_run_utc
                  ? `Next run: ${nextRunLabel()}`
                  : 'Enabled — configure run times below.'
                : 'Disabled — digests only run when triggered manually.'}
            </p>
          </div>
          <button
            type="button"
            disabled={togglingEnabled}
            onClick={handleToggleEnabled}
            class={[
              'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent',
              'transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2',
              enabled
                ? 'bg-teal-500'
                : 'bg-slate-200 dark:bg-slate-700',
              togglingEnabled ? 'opacity-50 cursor-not-allowed' : '',
            ].join(' ')}
            role="switch"
            aria-checked={enabled}
          >
            <span
              class={[
                'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0',
                'transition duration-200 ease-in-out',
                enabled ? 'translate-x-5' : 'translate-x-0',
              ].join(' ')}
            />
          </button>
        </div>
      </Card>

      {/* Timezone + run times */}
      <Card>
        <CardHeader
          title="Run times"
          description="Times are in your configured timezone (24-hour HH:MM). Save to apply changes."
        />
        <form onSubmit={handleSaveTimes} class="space-y-5">
          {/* Timezone select */}
          <div class="space-y-1.5">
            <label
              for="tz-select"
              class="block text-xs font-medium text-slate-600 dark:text-slate-400"
            >
              Timezone
            </label>
            <select
              id="tz-select"
              class={`${INPUT} w-full`}
              value={timezone}
              onChange={(e) => setTimezone((e.target as HTMLSelectElement).value)}
            >
              {!ALL_TIMEZONES.includes(timezone) && (
                <option value={timezone}>{timezone}</option>
              )}
              {Object.entries(TIMEZONE_GROUPS).map(([region, tzs]) => (
                <optgroup key={region} label={region}>
                  {tzs.map((tz) => (
                    <option key={tz} value={tz}>
                      {tz}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          {/* HH:MM time inputs */}
          <div class="space-y-2">
            <label class="block text-xs font-medium text-slate-600 dark:text-slate-400">
              Daily run times
            </label>
            {times.map((t, idx) => (
              <div key={idx} class="flex items-center gap-2">
                <input
                  type="text"
                  class={`${INPUT} w-28`}
                  placeholder="07:00"
                  value={t}
                  pattern="([01]\d|2[0-3]):[0-5]\d"
                  required
                  onInput={(e) =>
                    updateTime(idx, (e.target as HTMLInputElement).value)
                  }
                />
                {times.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeTime(idx)}
                    class="text-slate-400 hover:text-red-500 dark:hover:text-red-400 transition-colors text-sm px-1"
                    aria-label="Remove time"
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>

          <div class="flex items-center gap-3">
            <Button type="button" variant="secondary" size="sm" onClick={addTime}>
              Add time
            </Button>
            <Button type="submit" loading={savingTimes}>
              Save
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
