import type {
  AdminOverview,
  AdvisorPageData,
  ApiKey,
  DigestDetail,
  DigestEntry,
  Job,
  LlmConfig,
  PreferenceProfile,
  RatingArticle,
  Source,
} from './types';

/** Generic HTTP helper. Throws on non-2xx responses. */
async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const init: RequestInit = { method };
  if (body != null) {
    if (body instanceof FormData) {
      init.body = body;
    } else {
      init.headers = { 'Content-Type': 'application/json' };
      init.body = JSON.stringify(body);
    }
  }
  const res = await fetch(path, init);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${method} ${path} failed (${res.status}): ${text}`);
  }
  const ct = res.headers.get('content-type') ?? '';
  if (ct.includes('application/json')) {
    return res.json() as Promise<T>;
  }
  return undefined as T;
}

export const api = {
  // ---------- Digests --------------------------------------------------
  listDigests: () => request<DigestEntry[]>('GET', '/api/digests'),
  getLatestDigest: () =>
    request<DigestDetail | null>('GET', '/api/digests/latest'),
  getDigest: (id: number) =>
    request<DigestDetail>('GET', `/api/digests/${id}`),

  // ---------- Job -------------------------------------------------------
  getJobStatus: () => request<Job>('GET', '/api/digest/status'),
  runDigest: () =>
    request<{ ok: boolean; message: string; job: Job }>(
      'POST',
      '/api/digest/run',
    ),
  dismissJob: () => request<Job>('POST', '/api/digest/dismiss'),

  // ---------- Read tracking ---------------------------------------------
  getReadUrls: () => request<{ urls: string[] }>('GET', '/api/read'),
  markRead: (url: string, isRead: boolean) =>
    request<void>('POST', '/api/read', { url, read: isRead }),

  // ---------- Ratings ---------------------------------------------------
  getRatings: () => request<RatingArticle[]>('GET', '/api/ratings'),
  submitRating: (url: string, rating: number) =>
    request<void>('POST', '/api/ratings', { url, rating }),
  getPreferenceProfile: () =>
    request<PreferenceProfile>('GET', '/api/preferences/profile'),

  // ---------- Sources ---------------------------------------------------
  listSources: () => request<Source[]>('GET', '/api/sources'),
  addSource: (data: FormData) => request<Source>('POST', '/api/sources', data),
  deleteSource: (id: number) =>
    request<void>('DELETE', `/api/sources/${id}`),
  importOpml: (data: FormData) =>
    request<{ added: number }>('POST', '/api/sources/import-opml', data),
  exportOpmlUrl: () => '/api/sources/export.opml',

  // ---------- LLM Config ------------------------------------------------
  getLlmConfig: () => request<LlmConfig>('GET', '/api/config/llm'),
  saveLlmConfig: (data: Partial<LlmConfig>) =>
    request<void>('PUT', '/api/config/llm', data),
  pullOllamaModel: (model: string) =>
    request<{ message: string }>(
      'POST',
      '/api/config/llm/ollama/pull',
      { model },
    ),
  deleteOllamaModel: (model: string) =>
    request<{ message: string }>(
      'POST',
      '/api/config/llm/ollama/delete',
      { model },
    ),

  // ---------- API Keys --------------------------------------------------
  listKeys: () => request<ApiKey[]>('GET', '/api/config/keys'),
  saveKey: (service: string, key_value: string) =>
    request<void>('POST', '/api/config/keys', { service, key_value }),
  deleteKey: (service: string) =>
    request<void>('DELETE', `/api/config/keys/${service}`),

  // ---------- Admin -----------------------------------------------------
  getAdminOverview: () =>
    request<AdminOverview>('GET', '/api/admin/overview'),
  getAdvisor: () =>
    request<AdvisorPageData>('GET', '/api/admin/advisor'),
  applyAdvisor: (recommended_model: string) =>
    request<void>('POST', '/api/admin/advisor/apply', { recommended_model }),
};
