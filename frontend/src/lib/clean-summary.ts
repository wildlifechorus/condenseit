/**
 * Strip common LLM output artifacts from article summaries.
 *
 * Handles prefixes like:
 *   - "Here is a 2-3 sentence summary of the article:"
 *   - "Here is a summary in 2-3 sentences:"
 *   - "This is a brief summary of the article:"
 *
 * Handles suffixes like:
 *   - "\nNote: I focused on..."
 *
 * Also handles cases where the LLM returned (or the backend stored) a raw
 * JSON blob like { "tldr": "...", "key_takeaways": [...], "summary": "..." }.
 * The blob may be valid JSON or malformed/truncated output from an LLM that
 * ran out of tokens.  Both cases are handled.
 */
const PREFIX_RE =
  /^(?:here\s+is\s+(?:a\s+)?(?:\d+[-\u2013]\d+\s+sentence\s+)?(?:brief\s+)?summary[^:]*:|this\s+(?:is\s+(?:a|an)\s+)?(?:\d+[-\u2013]\d+\s+sentence\s+)?(?:brief\s+)?summary[^:]*:)\s*/i;

const NOTE_SUFFIX_RE = /\n+\s*note:\s.*/is;

/** Shape of a structured LLM summary that may be stored as raw JSON. */
export interface StructuredSummary {
  tldr?: string;
  key_takeaways?: string[];
  summary?: string;
}

/**
 * Walk the text starting just after `openQuoteIdx` (the position of the
 * opening `"`) and decode the JSON string value.  Handles escape sequences
 * and returns a partial value when the closing `"` is absent (truncated LLM
 * output).  Returns null only when no characters were collected at all.
 */
function extractQuotedValue(text: string, openQuoteIdx: number): string | null {
  let i = openQuoteIdx + 1;
  let value = '';

  while (i < text.length) {
    const ch = text[i];
    if (ch === '\\' && i + 1 < text.length) {
      const next = text[i + 1];
      if (next === 'n') { value += '\n'; }
      else if (next === 't') { value += '\t'; }
      else if (next === '"') { value += '"'; }
      else if (next === '\\') { value += '\\'; }
      else { value += next; }
      i += 2;
    } else if (ch === '"') {
      return value || null;
    } else {
      value += ch;
      i++;
    }
  }

  /* truncated: return whatever we collected */
  return value || null;
}

/**
 * Locate a JSON string field by name in a raw JSON-like text blob and return
 * its decoded value.  Works on both valid and malformed/truncated JSON.
 */
function extractJsonField(text: string, field: string): string | null {
  const needle = `"${field}"`;
  let searchFrom = 0;

  while (searchFrom < text.length) {
    const fieldIdx = text.indexOf(needle, searchFrom);
    if (fieldIdx === -1) return null;
    searchFrom = fieldIdx + needle.length;

    const colonIdx = text.indexOf(':', searchFrom);
    if (colonIdx === -1) return null;

    let valueStart = colonIdx + 1;
    while (valueStart < text.length && /\s/.test(text[valueStart])) {
      valueStart++;
    }

    if (valueStart >= text.length || text[valueStart] !== '"') {
      /* value is not a string (e.g. array) — keep searching */
      continue;
    }

    return extractQuotedValue(text, valueStart);
  }

  return null;
}

/**
 * Attempt to parse `raw` as a structured JSON summary object.
 *
 * Tries strict JSON.parse first.  When that fails (truncated output, trailing
 * commas, unquoted strings in arrays, etc.) it falls back to character-level
 * extraction so the UI always shows readable text instead of a raw blob.
 *
 * Returns an object with at least one prose field when found, otherwise null.
 */
export function tryParseStructuredSummary(
  raw: string,
): StructuredSummary | null {
  if (!raw) return null;
  const trimmed = raw.trim();
  if (!trimmed.startsWith('{')) return null;

  /* --- fast path: valid JSON --- */
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      !Array.isArray(parsed)
    ) {
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
                (k): k is string => typeof k === 'string',
              )
            : undefined,
          summary:
            typeof obj['summary'] === 'string' ? obj['summary'] : undefined,
        };
      }
    }
  } catch {
    /* fall through to lenient extraction */
  }

  /* --- fallback: lenient extraction for malformed/truncated JSON blobs --- */
  const tldr = extractJsonField(trimmed, 'tldr') ?? undefined;
  const summary = extractJsonField(trimmed, 'summary') ?? undefined;

  if (tldr !== undefined || summary !== undefined) {
    return { tldr, summary };
  }

  return null;
}

export function cleanSummary(raw: string): string {
  if (!raw) return '';

  /* If the raw value is a JSON-structured summary blob, extract the prose. */
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
