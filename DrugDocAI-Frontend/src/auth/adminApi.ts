/**
 * adminApi.ts — Admin API key session management and authenticated fetch.
 *
 * The admin API key is obtained at login by validating it against the backend
 * probe endpoint (GET /admin/auth/check).  It is stored in sessionStorage only
 * (never localStorage, never a VITE_* env var, never hardcoded) so it is
 * automatically cleared when the browser tab is closed.
 *
 * Use `getAdminKey()` / `setAdminKey()` / `clearAdminKey()` to manage the key.
 * Use `adminFetch()` as a drop-in for `fetch()` when calling a protected endpoint
 * — it automatically injects the X-Admin-Key header.
 */

const SESSION_KEY = "drugdoc_admin_api_key";

/** Read the admin API key from sessionStorage. Returns null if not set. */
export function getAdminKey(): string | null {
  return sessionStorage.getItem(SESSION_KEY);
}

/** Persist the admin API key to sessionStorage for the duration of this tab. */
export function setAdminKey(key: string): void {
  sessionStorage.setItem(SESSION_KEY, key);
}

/** Remove the admin API key from sessionStorage (call on logout). */
export function clearAdminKey(): void {
  sessionStorage.removeItem(SESSION_KEY);
}

/** True if the admin API key is currently stored in this tab's sessionStorage. */
export function isAdminKeyPresent(): boolean {
  return !!sessionStorage.getItem(SESSION_KEY);
}

/**
 * A thin wrapper around `fetch` that automatically adds `X-Admin-Key` from
 * sessionStorage.  Use this only for protected backend endpoints
 * (POST /ingest, DELETE /documents/{filename}).
 *
 * If no key is stored the request is still sent — the backend will return 401,
 * which the caller can handle in the normal error path.
 */
export async function adminFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const key = getAdminKey();
  const headers = new Headers(init?.headers);

  if (key) {
    headers.set("X-Admin-Key", key);
  }

  return fetch(input, { ...init, headers });
}

/**
 * Validate an API key against the backend probe endpoint.
 * Returns an object describing the outcome so callers can show a
 * user-friendly error without exposing the key or backend internals.
 */
export async function validateAdminKey(
  apiBase: string,
  key: string
): Promise<
  | { ok: true }
  | { ok: false; status: number; userMessage: string }
> {
  try {
    const res = await fetch(`${apiBase}/admin/auth/check`, {
      method: "GET",
      headers: { "X-Admin-Key": key },
    });

    if (res.ok) {
      return { ok: true };
    }

    if (res.status === 503) {
      return {
        ok: false,
        status: 503,
        userMessage:
          "Server authentication is not configured. Contact your system administrator.",
      };
    }

    if (res.status === 401 || res.status === 403) {
      return {
        ok: false,
        status: res.status,
        userMessage: "Invalid admin credentials. Please try again.",
      };
    }

    return {
      ok: false,
      status: res.status,
      userMessage: `Authentication failed (server returned ${res.status}).`,
    };
  } catch {
    return {
      ok: false,
      status: 0,
      userMessage:
        "Unable to reach the authentication server. Check that the backend is running.",
    };
  }
}
