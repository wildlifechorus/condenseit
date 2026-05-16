const PREFIX_RE =
  /^(?:here\s+is\s+(?:a\s+)?(?:\d+[-\u2013]\d+\s+sentence\s+)?(?:brief\s+)?summary[^:]*:|this\s+(?:is\s+(?:a|an)\s+)?(?:\d+[-\u2013]\d+\s+sentence\s+)?(?:brief\s+)?summary[^:]*:)\s*/i;

const NOTE_SUFFIX_RE = /\n+\s*note:\s.*/is;

export interface StructuredSummary {
  tldr?: string;
  key_takeaways?: string[];
  summary?: string;
}

export function tryParseStructuredSummary(
  raw: string,
): StructuredSummary | null {
  if (!raw) {
    return null;
  }

  const trimmed = raw.trim();
  if (!trimmed.startsWith('{')) {
    return null;
  }

  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
      const obj = parsed as Record<string, unknown>;
      const keyTakeaways = obj['key_takeaways'];
      if (
        typeof obj['summary'] === 'string' ||
        typeof obj['tldr'] === 'string'
      ) {
        return {
          tldr: typeof obj['tldr'] === 'string' ? obj['tldr'] : undefined,
          key_takeaways: Array.isArray(keyTakeaways)
            ? keyTakeaways.filter(
                (takeaway): takeaway is string => typeof takeaway === 'string',
              )
            : undefined,
          summary:
            typeof obj['summary'] === 'string' ? obj['summary'] : undefined,
        };
      }
    }
  } catch {
    /* not valid JSON, fall through */
  }
  return null;
}

export function cleanSummary(raw: string): string {
  if (!raw) {
    return '';
  }

  const structured = tryParseStructuredSummary(raw);
  if (structured) {
    const text = structured.summary ?? structured.tldr ?? '';
    return text.trim();
  }

  let s = raw.trim();
  s = s.replace(PREFIX_RE, '');
  s = s.replace(NOTE_SUFFIX_RE, '');
  return s.trim();
}
