import { Link, useLocation } from 'wouter';
import type { DigestEntry } from '../lib/types';

interface SidebarProps {
  digests: DigestEntry[];
  currentDigestId?: number | null;
  onClose?: () => void;
}

interface NavSection {
  label: string;
  links: Array<{ href: string; label: string; exact?: boolean }>;
}

const SECTIONS: NavSection[] = [
  {
    label: 'Read',
    links: [{ href: '/', label: 'Latest digest', exact: true }],
  },
  {
    label: 'Configure',
    links: [
      { href: '/admin/sources', label: 'Sources' },
      { href: '/admin/llm', label: 'LLM' },
      { href: '/admin/keys', label: 'API keys' },
      { href: '/admin/schedule', label: 'Schedule' },
      { href: '/admin/settings', label: 'Digest' },
      { href: '/admin/preferences', label: 'Profile' },
      { href: '/admin/security', label: 'Security' },
      { href: '/admin/budget', label: 'Budget' },
      { href: '/admin/logs', label: 'Logs' },
    ],
  },
];

/**
 * Left navigation sidebar.
 * Shows nav sections + recent digest history.
 */
export function Sidebar({
  digests,
  currentDigestId,
  onClose,
}: SidebarProps) {
  const [location] = useLocation();

  function isActive(href: string, exact = false): boolean {
    if (exact) return location === href;
    return location === href || location.startsWith(href + '/');
  }

  function handleLinkClick() {
    onClose?.();
  }

  return (
    <aside class="flex flex-col h-full overflow-y-auto bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-700 py-4 px-3 gap-1">
      {SECTIONS.map((section) => (
        <div key={section.label} class="mb-4">
          <p class="px-3 mb-1 text-xs font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
            {section.label}
          </p>

          {section.links.map(({ href, label, exact }) => (
            <Link
              key={href}
              href={href}
              onClick={handleLinkClick}
              class={[
                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors no-underline',
                isActive(href, exact)
                  ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100',
              ].join(' ')}
            >
              {label}
            </Link>
          ))}

          {/* Digest history under "Read" */}
          {section.label === 'Read' && digests.length > 0 && (
            <ul class="mt-1 space-y-0.5">
              {digests.slice(0, 8).map((d) => (
                <li key={d.id}>
                  <Link
                    href={`/?id=${d.id}`}
                    onClick={handleLinkClick}
                    class={[
                      'flex items-center px-3 py-1.5 rounded-lg text-xs transition-colors no-underline truncate',
                      currentDigestId === d.id
                        ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 font-semibold'
                        : 'text-slate-500 dark:text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-300',
                    ].join(' ')}
                  >
                    #{d.id} · {d.created_at.slice(0, 10)}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </aside>
  );
}
