import { useState } from 'preact/hooks';
import type { ComponentChildren } from 'preact';
import { Header } from '../components/Header';
import { Sidebar } from '../components/Sidebar';
import type { DigestEntry } from '../lib/types';

interface AppLayoutProps {
  children: ComponentChildren;
  digests: DigestEntry[];
  currentDigestId?: number | null;
}

/**
 * Full admin/digest layout: sticky header + collapsible sidebar + content area.
 * On desktop (lg+) the sidebar is always visible.
 * On mobile it slides in from the left as an overlay.
 */
export function AppLayout({
  children,
  digests,
  currentDigestId,
}: AppLayoutProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div class="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-950">
      <Header
        onMobileMenuToggle={() => setMenuOpen((o) => !o)}
        mobileMenuOpen={menuOpen}
      />

      {/* Mobile overlay */}
      {menuOpen && (
        <div
          class="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setMenuOpen(false)}
        />
      )}

      {/* Body */}
      <div class="flex flex-1 min-h-0">
        {/* Sidebar - desktop always, mobile slide-in */}
        <div
          class={[
            'fixed lg:static inset-y-0 left-0 z-30 w-60 transition-transform duration-200',
            'lg:translate-x-0 lg:top-0',
            menuOpen ? 'translate-x-0' : '-translate-x-full',
            /* On mobile, push down below header */
            'top-14',
          ].join(' ')}
        >
          <Sidebar
            digests={digests}
            currentDigestId={currentDigestId}
            onClose={() => setMenuOpen(false)}
          />
        </div>

        {/* Main content */}
        <main class="flex-1 min-w-0 p-5 lg:pl-5 overflow-auto">
          <div class="max-w-5xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
}
