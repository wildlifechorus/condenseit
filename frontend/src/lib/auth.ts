/**
 * Auth API helpers.
 *
 * All requests use `credentials: 'include'` so the signed session cookie is
 * sent automatically, even when the dev proxy and the API run on different
 * ports.
 */

/** Shape returned by GET /api/auth/check. */
export interface AuthCheckResult {
  authenticated: boolean;
}

/**
 * Check whether the current session cookie is valid.
 * Returns `true` when authenticated, `false` when not.
 * Throws only on network errors (not on 401 responses).
 */
export async function checkAuth(): Promise<boolean> {
  const res = await fetch('/api/auth/check', {
    method: 'GET',
    credentials: 'include',
  });
  if (res.status === 401) {
    return false;
  }
  if (!res.ok) {
    throw new Error(`Auth check failed (${res.status})`);
  }
  return true;
}

/**
 * Attempt to log in with the given password.
 * Returns `null` on success, or an error message string on failure.
 */
export async function login(password: string): Promise<string | null> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });

  if (res.ok) {
    return null;
  }

  if (res.status === 401) {
    return 'Incorrect password. Please try again.';
  }

  const text = await res.text().catch(() => res.statusText);
  return `Login failed (${res.status}): ${text}`;
}

/**
 * Clear the current session.
 * Does not throw; a best-effort fire-and-forget is acceptable for logout.
 */
export async function logout(): Promise<void> {
  await fetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'include',
  }).catch(() => {});
}
