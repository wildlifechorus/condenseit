import type {
  ApiKey,
  BudgetData,
  BudgetLimits,
  DigestConfig,
  DigestDetail,
  DigestEntry,
  DigestItem,
  Job,
  LlmConfig,
  PasswordInfo,
  PreferenceProfile,
  RatingArticle,
  RankingWeights,
  ReadLaterItem,
  RunLog,
  RunLogSummary,
  ScheduleConfig,
  SchedulerStatus,
  Source,
} from './types';

/** Generic HTTP helper. Throws on non-2xx responses. */
async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const init: RequestInit = { method, credentials: 'include' };
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
    if (res.status === 401) {
      window.dispatchEvent(new CustomEvent('auth:expired'));
    }
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
  // Digests
  listDigests: () => request<DigestEntry[]>('GET', '/api/digests'),
  getLatestDigest: () =>
    request<DigestDetail | null>('GET', '/api/digests/latest'),
  getDigest: (id: number) =>
    request<DigestDetail>('GET', `/api/digests/${id}`),

  // Job
  getJobStatus: () => request<Job>('GET', '/api/digest/status'),
  runDigest: () =>
    request<{ ok: boolean; message: string; job: Job }>(
      'POST',
      '/api/digest/run',
    ),
  dismissJob: () => request<Job>('POST', '/api/digest/dismiss'),

  // Read tracking
  getReadUrls: () => request<{ urls: string[] }>('GET', '/api/read'),
  markRead: (url: string, isRead: boolean) =>
    request<void>('POST', '/api/read', { url, read: isRead }),

  // Dismiss (negative implicit signal + mark as read)
  dismissArticle: (url: string, title?: string) =>
    request<void>('POST', '/api/dismiss', { url, title: title ?? '' }),

  // Ratings
  getRatings: () => request<RatingArticle[]>('GET', '/api/ratings'),
  submitRating: (url: string, rating: number) =>
    request<void>('POST', '/api/ratings', { url, rating }),
  getPreferenceProfile: () =>
    request<PreferenceProfile>('GET', '/api/preferences/profile'),

  // Ranking weights (admin-tunable)
  getRankingWeights: () =>
    request<RankingWeights>('GET', '/api/preferences/weights'),
  saveRankingWeights: (data: Partial<RankingWeights>) =>
    request<void>('PUT', '/api/preferences/weights', data),

  // Sources
  listSources: () => request<Source[]>('GET', '/api/sources'),
  addSource: (data: FormData) =>
    request<{ ok: boolean }>('POST', '/api/sources', data),
  updateSource: (id: number, data: FormData) =>
    request<{ ok: boolean }>('PUT', `/api/sources/${id}`, data),
  deleteSource: (id: number) =>
    request<void>('DELETE', `/api/sources/${id}`),
  toggleSource: (id: number, enabled: boolean) =>
    request<{ ok: boolean }>(
      'PATCH',
      `/api/sources/${id}/toggle`,
      { enabled },
    ),
  importOpml: (data: FormData) =>
    request<{ added: number }>('POST', '/api/sources/import-opml', data),
  exportOpmlUrl: () => '/api/sources/export.opml',

  // LLM config
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

  // API keys
  listKeys: () => request<ApiKey[]>('GET', '/api/config/keys'),
  saveKey: (service: string, key_value: string) =>
    request<void>('POST', '/api/config/keys', { service, key_value }),
  deleteKey: (service: string) =>
    request<void>('DELETE', `/api/config/keys/${service}`),

  // Budget
  getBudget: () => request<BudgetData>('GET', '/api/config/budget'),
  getBudgetLimits: () =>
    request<BudgetLimits>('GET', '/api/config/budget-limits'),
  saveBudgetLimits: (data: BudgetLimits) =>
    request<void>('PUT', '/api/config/budget-limits', data),

  // Scheduler
  getSchedulerStatus: () =>
    request<SchedulerStatus>('GET', '/api/scheduler/status'),

  // Schedule config
  getScheduleConfig: () =>
    request<ScheduleConfig>('GET', '/api/config/schedule'),
  saveScheduleConfig: (payload: { times?: string[]; enabled?: boolean }) =>
    request<{ ok: boolean }>('PUT', '/api/config/schedule', payload),

  // Digest pipeline settings
  getDigestConfig: () =>
    request<DigestConfig>('GET', '/api/config/digest'),
  saveDigestConfig: (data: Partial<DigestConfig>) =>
    request<void>('PUT', '/api/config/digest', data),

  // Security
  getPasswordInfo: () =>
    request<PasswordInfo>('GET', '/api/config/password-info'),
  changePassword: (current_password: string, new_password: string) =>
    request<void>('PUT', '/api/config/password', {
      current_password,
      new_password,
    }),

  // Run logs
  listLogs: () => request<RunLogSummary[]>('GET', '/api/logs'),
  getLog: (id: number) => request<RunLog | null>('GET', `/api/logs/${id}`),
  getLatestLog: () => request<RunLog | null>('GET', '/api/logs/latest'),

  // Read Later
  getReadLaterItems: () =>
    request<{ items: ReadLaterItem[] }>('GET', '/api/read-later'),
  getReadLaterUrls: () =>
    request<{ urls: string[] }>('GET', '/api/read-later/urls'),
  saveReadLater: (item: DigestItem) =>
    request<void>('POST', '/api/read-later', item),
  removeReadLater: (url: string) =>
    request<void>('DELETE', '/api/read-later', { url }),
};
