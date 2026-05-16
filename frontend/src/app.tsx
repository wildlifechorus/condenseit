import { useState, useCallback, useEffect } from 'preact/hooks';
import { Router, Route, Switch, Redirect } from 'wouter';

import { AppLayout } from './layouts/AppLayout';
import { DigestPage } from './pages/Digest';
import { LoginPage } from './pages/Login';
import { SourcesPage } from './pages/admin/Sources';
import { LlmConfigPage } from './pages/admin/LlmConfig';
import { ApiKeysPage } from './pages/admin/ApiKeys';
import { BudgetPage } from './pages/admin/Budget';
import { SchedulePage } from './pages/admin/Schedule';
import { LogsPage } from './pages/admin/Logs';
import { SettingsPage } from './pages/admin/Settings';
import { PreferencesPage } from './pages/admin/Preferences';
import { SecurityPage } from './pages/admin/Security';
import { api } from './lib/api';
import { checkAuth } from './lib/auth';
import type { DigestEntry } from './lib/types';

/** Possible auth states while the app determines whether a session is active. */
type AuthState = 'checking' | 'authenticated' | 'unauthenticated';

export function App() {
  const [digests, setDigests] = useState<DigestEntry[]>([]);
  const [currentDigestId, setCurrentDigestId] = useState<number | null>(null);
  const [authState, setAuthState] = useState<AuthState>('checking');

  useEffect(() => {
    checkAuth()
      .then((ok) => setAuthState(ok ? 'authenticated' : 'unauthenticated'))
      .catch(() => setAuthState('unauthenticated'));
  }, []);

  useEffect(() => {
    const handleExpired = () => setAuthState('unauthenticated');
    window.addEventListener('auth:expired', handleExpired);
    return () => window.removeEventListener('auth:expired', handleExpired);
  }, []);

  useEffect(() => {
    if (authState === 'authenticated') {
      api.listDigests().then(setDigests).catch(() => {});
    }
  }, [authState]);

  const handleDigestLoaded = useCallback((id: number | null) => {
    setCurrentDigestId(id);
  }, []);

  const handleLogin = useCallback(() => {
    setAuthState('authenticated');
  }, []);

  if (authState === 'checking') {
    return (
      <div class='min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950'>
        <span class='w-8 h-8 rounded-full border-4 border-teal-500 border-t-transparent animate-spin' />
      </div>
    );
  }

  if (authState === 'unauthenticated') {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <Router>
      <AppLayout digests={digests} currentDigestId={currentDigestId}>
        <Switch>
          <Route path="/">
            <DigestPage onDigestLoaded={handleDigestLoaded} />
          </Route>
          <Route path="/admin">
            <Redirect to="/admin/sources" />
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
          <Route path="/admin/budget">
            <BudgetPage />
          </Route>
          <Route path="/admin/schedule">
            <SchedulePage />
          </Route>
          <Route path="/admin/logs">
            <LogsPage />
          </Route>
          <Route path="/admin/settings">
            <SettingsPage />
          </Route>
          <Route path="/admin/preferences">
            <PreferencesPage />
          </Route>
          <Route path="/admin/security">
            <SecurityPage />
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
