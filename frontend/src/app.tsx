import { useState, useCallback } from 'preact/hooks';
import { Router, Route, Switch } from 'wouter';

import { AppLayout } from './layouts/AppLayout';
import { PwaLayout } from './layouts/PwaLayout';
import { DigestPage } from './pages/Digest';
import { LoginPage } from './pages/Login';
import { AdminOverviewPage } from './pages/admin/Overview';
import { SourcesPage } from './pages/admin/Sources';
import { LlmConfigPage } from './pages/admin/LlmConfig';
import { ApiKeysPage } from './pages/admin/ApiKeys';
import { AdvisorPage } from './pages/admin/Advisor';
import { api } from './lib/api';
import { checkAuth } from './lib/auth';
import type { DigestEntry } from './lib/types';
import { useEffect } from 'preact/hooks';

const IS_PWA = import.meta.env.MODE === 'pwa';

/** Possible auth states while the app determines whether a session is active. */
type AuthState = 'checking' | 'authenticated' | 'unauthenticated';

export function App() {
  const [digests, setDigests] = useState<DigestEntry[]>([]);
  const [currentDigestId, setCurrentDigestId] = useState<number | null>(null);
  const [authState, setAuthState] = useState<AuthState>('checking');

  useEffect(() => {
    // Probe the session cookie on every cold start.  The server returns 200
    // when authenticated (or when no password is configured), 401 otherwise.
    checkAuth()
      .then((ok) => setAuthState(ok ? 'authenticated' : 'unauthenticated'))
      .catch(() => setAuthState('unauthenticated'));
  }, []);

  useEffect(() => {
    // Listen for 401 responses dispatched by the API helper so that an
    // expired or cleared session mid-use returns to the login page.
    const handleExpired = () => setAuthState('unauthenticated');
    window.addEventListener('auth:expired', handleExpired);
    return () => window.removeEventListener('auth:expired', handleExpired);
  }, []);

  useEffect(() => {
    if (!IS_PWA && authState === 'authenticated') {
      api.listDigests().then(setDigests).catch(() => {});
    }
  }, [authState]);

  const handleDigestLoaded = useCallback((id: number | null) => {
    setCurrentDigestId(id);
  }, []);

  const handleLogin = useCallback(() => {
    setAuthState('authenticated');
  }, []);

  // Show a minimal spinner while the auth check request is in flight.
  if (authState === 'checking') {
    return (
      <div class='min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950'>
        <span class='w-8 h-8 rounded-full border-4 border-teal-500 border-t-transparent animate-spin' />
      </div>
    );
  }

  // Show login form when the session is absent or expired.
  if (authState === 'unauthenticated') {
    return <LoginPage onLogin={handleLogin} />;
  }

  if (IS_PWA) {
    return (
      <Router>
        <PwaLayout>
          <DigestPage onDigestLoaded={handleDigestLoaded} />
        </PwaLayout>
      </Router>
    );
  }

  return (
    <Router>
      <AppLayout digests={digests} currentDigestId={currentDigestId}>
        <Switch>
          <Route path="/">
            <DigestPage onDigestLoaded={handleDigestLoaded} />
          </Route>
          <Route path="/admin">
            <AdminOverviewPage />
          </Route>
          <Route path="/admin/sources">
            <SourcesPage />
          </Route>
          <Route path="/admin/llm">
            <LlmConfigPage />
          </Route>
          <Route path="/admin/keys">
            <ApiKeysPage />
          </Route>
          <Route path="/admin/advisor">
            <AdvisorPage />
          </Route>
          <Route>
            <div class="py-20 text-center text-slate-500 dark:text-slate-400">
              Page not found.
            </div>
          </Route>
        </Switch>
      </AppLayout>
    </Router>
  );
}
