import { useState, useCallback } from 'preact/hooks';
import { Router, Route, Switch } from 'wouter';
import { AppLayout } from './layouts/AppLayout';
import { PwaLayout } from './layouts/PwaLayout';
import { DigestPage } from './pages/Digest';
import { AdminOverviewPage } from './pages/admin/Overview';
import { SourcesPage } from './pages/admin/Sources';
import { LlmConfigPage } from './pages/admin/LlmConfig';
import { ApiKeysPage } from './pages/admin/ApiKeys';
import { AdvisorPage } from './pages/admin/Advisor';
import { api } from './lib/api';
import type { DigestEntry } from './lib/types';
import { useEffect } from 'preact/hooks';

const IS_PWA = import.meta.env.MODE === 'pwa';

export function App() {
  const [digests, setDigests] = useState<DigestEntry[]>([]);
  const [currentDigestId, setCurrentDigestId] = useState<number | null>(null);

  useEffect(() => {
    if (!IS_PWA) {
      api.listDigests().then(setDigests).catch(() => {});
    }
  }, []);

  const handleDigestLoaded = useCallback((id: number | null) => {
    setCurrentDigestId(id);
  }, []);

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
