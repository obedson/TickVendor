const API_ORIGIN = (import.meta.env.VITE_API_ORIGIN || '').replace(/\/$/, '');
export const API_BASE = `${API_ORIGIN}/api/v1`;
export class ApiError extends Error { constructor(public readonly status: number, message: string, public readonly kind: 'auth' | 'forbidden' | 'server' | 'unexpected' | 'network') { super(message); } }
export function apiUrl(path: string): string { return `${API_BASE}/${path.replace(/^\//, '')}`; }
export function authHeaders(token?: string): HeadersInit { return token ? { Authorization: `Bearer ${token}` } : {}; }
async function responseMessage(response: Response, fallback: string): Promise<string> { const contentType = response.headers.get('content-type') || ''; if (contentType.includes('application/json')) { const body = await response.json().catch(() => null); if (typeof body?.detail === 'string') return body.detail; if (typeof body?.message === 'string') return body.message; } return fallback; }
export async function apiFetch(path: string, init: RequestInit = {}, token?: string): Promise<Response> { const headers = new Headers(init.headers); if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`); return fetch(apiUrl(path), { ...init, headers }); }

// ── Central auth state ────────────────────────────────────────────────────────
// Single source of truth for the live access token. Components receive the
// token via props but the canonical live value lives here so that a refresh
// updates every in-flight and subsequent request without stale closures.

export type SessionData = { access_token: string; refresh_token: string; user: { id: string; email: string; role: string; username: string; display_name: string } };

// Callbacks registered by the React root to react to token changes / sign-out.
type AuthListener = (session: SessionData | null) => void;
const authListeners = new Set<AuthListener>();
export function addAuthListener(fn: AuthListener): () => void { authListeners.add(fn); return () => authListeners.delete(fn); }
function notifyAuth(session: SessionData | null): void { authListeners.forEach(fn => fn(session)); }

// Persist + broadcast a refreshed session.
export function persistSession(session: SessionData): void {
  sessionStorage.setItem('tickvendor.session', JSON.stringify(session));
  notifyAuth(session);
}

// Clear session and broadcast sign-out.
export function clearSession(): void {
  sessionStorage.removeItem('tickvendor.session');
  notifyAuth(null);
}

// Read the current live access token from storage (always fresh, no closure).
export function getLiveToken(): string | undefined {
  try {
    const raw = sessionStorage.getItem('tickvendor.session');
    if (!raw) return undefined;
    return (JSON.parse(raw) as SessionData).access_token;
  } catch { return undefined; }
}

// Single in-flight refresh promise — prevents concurrent refresh races.
let _refreshPromise: Promise<string | undefined> | null = null;

async function doRefresh(): Promise<string | undefined> {
  const raw = sessionStorage.getItem('tickvendor.session');
  if (!raw) return undefined;
  let current: SessionData;
  try { current = JSON.parse(raw) as SessionData; } catch { return undefined; }
  if (!current.refresh_token) return undefined;
  const response = await fetch(apiUrl('auth/refresh'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: current.refresh_token }),
  });
  if (!response.ok) {
    // Invalid refresh token → clean sign-out.
    clearSession();
    return undefined;
  }
  const next = await response.json() as SessionData;
  // Preserve user object from current session if not returned by refresh.
  const merged: SessionData = { ...current, ...next };
  persistSession(merged);
  return merged.access_token;
}

// Deduplicated refresh: at most one in-flight refresh at a time.
function refreshSession(): Promise<string | undefined> {
  if (!_refreshPromise) {
    _refreshPromise = doRefresh().finally(() => { _refreshPromise = null; });
  }
  return _refreshPromise;
}

// ── Body re-readability guard ─────────────────────────────────────────────────
// FormData and ReadableStream bodies can only be consumed once. Retrying a
// request with such a body would silently send an empty body. Detect these
// cases and skip the retry rather than sending a corrupt request.
function isBodyReReadable(body: BodyInit | null | undefined): boolean {
  if (body == null) return true;
  if (typeof body === 'string') return true;
  if (body instanceof URLSearchParams) return true;
  if (body instanceof ArrayBuffer) return true;
  if (body instanceof Blob) return true;
  // FormData and ReadableStream are NOT safely re-readable.
  return false;
}

// ── Core API fetch with automatic 401 → refresh → single retry ───────────────
export async function apiJson<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  // Always use the freshest token from storage, falling back to the prop.
  const liveToken = getLiveToken() ?? token;
  // Skip refresh-on-401 retry for non-re-readable bodies (FormData/streams)
  // to avoid double-consumption. Callers using FormData should handle 401 themselves.
  const canRetry = isBodyReReadable(init.body);
  // Never attempt a refresh for the auth endpoints themselves.
  const isAuthPath = /^auth\/(login|refresh)/.test(path.replace(/^\//, ''));
  let response: Response;
  try { response = await apiFetch(path, init, liveToken); } catch {
    throw new ApiError(0, 'Unable to reach TickVendor. Check your connection and try again.', 'network');
  }
  if (response.status === 401 && liveToken && canRetry && !isAuthPath) {
    // Attempt a single refresh; concurrent callers share the same promise.
    const refreshed = await refreshSession().catch(() => undefined);
    if (refreshed) {
      // Retry the original request exactly once with the new token.
      try { response = await apiFetch(path, init, refreshed); } catch {
        throw new ApiError(0, 'Unable to reach TickVendor. Check your connection and try again.', 'network');
      }
      // If the retry also returns 401, the session is truly expired — sign out.
      if (response.status === 401) {
        clearSession();
      }
    }
  }
  if (!response.ok) {
    const kind = response.status === 401 ? 'auth' : response.status === 403 ? 'forbidden' : response.status >= 500 ? 'server' : 'unexpected';
    const fallback = kind === 'auth' ? 'Your session has expired. Please sign in again.' : kind === 'forbidden' ? 'You do not have access to this information.' : 'TickVendor could not load this information. Please try again.';
    throw new ApiError(response.status, await responseMessage(response, fallback), kind);
  }
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) throw new ApiError(response.status, 'TickVendor returned an unexpected response. Please try again.', 'unexpected');
  try { return await response.json() as T; } catch { throw new ApiError(response.status, 'TickVendor returned unreadable data. Please try again.', 'unexpected'); }
}

// ── Authenticated apiFetch wrapper with refresh-on-401 ───────────────────────
// Use this for non-JSON responses (file uploads, etc.) that still need auth.
// NOTE: Does NOT retry FormData/stream bodies to avoid double-consumption.
export async function apiFetchAuth(path: string, init: RequestInit = {}, token?: string): Promise<Response> {
  const liveToken = getLiveToken() ?? token;
  const canRetry = isBodyReReadable(init.body);
  let response: Response;
  try { response = await apiFetch(path, init, liveToken); } catch {
    throw new ApiError(0, 'Unable to reach TickVendor. Check your connection and try again.', 'network');
  }
  if (response.status === 401 && liveToken && canRetry) {
    const refreshed = await refreshSession().catch(() => undefined);
    if (refreshed) {
      try { response = await apiFetch(path, init, refreshed); } catch {
        throw new ApiError(0, 'Unable to reach TickVendor. Check your connection and try again.', 'network');
      }
      if (response.status === 401) {
        clearSession();
      }
    }
  }
  return response;
}
