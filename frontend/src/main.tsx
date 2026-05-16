import { render } from 'preact';
import { registerSW } from 'virtual:pwa-register';
import { App } from './app';
import './index.css';

/**
 * Register the service worker and wire up two reliability behaviours:
 *
 * 1. Periodic update check (every 60 min): ensures a long-lived PWA tab
 *    discovers new deploys even without a navigation event.
 *
 * 2. Auto-reload on controllerchange: when the new SW calls clients.claim()
 *    the browser fires controllerchange on every open client. We reload so
 *    the page is served by the new SW immediately, rather than leaving the
 *    user on stale JS/HTML until they manually hard-refresh.
 */
registerSW({
  immediate: true,
  onRegisteredSW(_swUrl, registration) {
    if (!registration) return;
    /** Poll for SW updates once per hour. */
    setInterval(() => registration.update(), 60 * 60 * 1000);
  },
});

let _reloading = false;
navigator.serviceWorker?.addEventListener('controllerchange', () => {
  if (_reloading) return;
  _reloading = true;
  window.location.reload();
});

render(<App />, document.getElementById('app')!);
