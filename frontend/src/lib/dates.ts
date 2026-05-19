/** YYYY-MM-DD in the user's local timezone (for date-range filters). */
export function localDateKey(iso?: string): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
    const parts = new Intl.DateTimeFormat('en-CA', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(d);
    const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
    return `${get('year')}-${get('month')}-${get('day')}`;
  } catch {
    return iso.slice(0, 10);
  }
}

/** Locale-aware calendar date (no time). */
export function formatDateOnly(
  iso?: string,
  opts: { year?: boolean } = {},
): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
    return new Intl.DateTimeFormat(undefined, {
      day: 'numeric',
      month: 'short',
      ...(opts.year ? { year: 'numeric' } : {}),
    }).format(d);
  } catch {
    return iso.slice(0, 10);
  }
}

/** Format a UTC ISO timestamp for the digest sidebar (locale date/time, local TZ). */
export function formatDigestLabel(utcIso: string): string {
  try {
    const d = new Date(utcIso);
    if (Number.isNaN(d.getTime())) {
      return utcIso.slice(0, 16).replace('T', ' ');
    }
    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(d);
  } catch {
    return utcIso.slice(0, 16).replace('T', ' ');
  }
}

/** Format a UTC ISO timestamp for the digest page subtitle (with TZ abbreviation). */
export function formatDigestSubtitle(utcIso: string): string {
  try {
    const d = new Date(utcIso);
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const parts = new Intl.DateTimeFormat(undefined, {
      timeZone: tz,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).formatToParts(d);
    const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
    const dateStr = `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}`;
    const tzAbbr =
      new Intl.DateTimeFormat(undefined, {
        timeZone: tz,
        timeZoneName: 'short',
      })
        .formatToParts(d)
        .find((p) => p.type === 'timeZoneName')?.value ?? tz;
    return `${dateStr} ${tzAbbr}`;
  } catch {
    return utcIso.slice(0, 16).replace('T', ' ') + ' UTC';
  }
}
