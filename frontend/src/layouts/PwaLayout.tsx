import type { ComponentChildren } from 'preact';
import { Header } from '../components/Header';

interface PwaLayoutProps {
  children: ComponentChildren;
  title?: string;
  date?: string;
}

/**
 * Minimal layout for the static PWA:
 * header-only (no sidebar, no run button), centred content.
 */
export function PwaLayout({ children, title, date }: PwaLayoutProps) {
  return (
    <div class="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-950">
      <Header isPwa pwaTitle={title} pwaDate={date} />
      <main class="flex-1 w-full max-w-5xl mx-auto px-4 py-5">{children}</main>
    </div>
  );
}
