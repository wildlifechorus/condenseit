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
 */
const PREFIX_RE =
  /^(?:here\s+is\s+(?:a\s+)?(?:\d+[-\u2013]\d+\s+sentence\s+)?(?:brief\s+)?summary[^:]*:|this\s+(?:is\s+(?:a|an)\s+)?(?:\d+[-\u2013]\d+\s+sentence\s+)?(?:brief\s+)?summary[^:]*:)\s*/i;

const NOTE_SUFFIX_RE = /\n+\s*note:\s.*/is;

export function cleanSummary(raw: string): string {
  if (!raw) return '';
  let s = raw.trim();
  s = s.replace(PREFIX_RE, '');
  s = s.replace(NOTE_SUFFIX_RE, '');
  return s.trim();
}
