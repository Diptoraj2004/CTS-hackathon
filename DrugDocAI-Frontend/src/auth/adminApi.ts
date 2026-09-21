/** Bearer-token storage and authenticated requests for protected admin APIs. */
const TOKEN_KEY = "drugdoc_auth_token";

export function getAuthToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}
export function setAuthToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

/** Remove the bearer token from this browser tab. */
export function clearAdminKey(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

/** True if a bearer token is currently stored in this tab. */
export function isAdminKeyPresent(): boolean {
  return !!sessionStorage.getItem(TOKEN_KEY);
}

/**
 * A thin wrapper around fetch that injects the bearer token when available.
 */
export async function adminFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const headers = new Headers(init?.headers);
  const token = getAuthToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return fetch(input, { ...init, headers });
}

