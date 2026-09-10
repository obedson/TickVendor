/**
 * Focused unit tests for api.ts — refresh-on-401, single retry, concurrent
 * dedup, failed-refresh sign-out, and FormData body guard.
 *
 * Framework: vitest (add `vitest` to devDependencies and configure in vite.config.ts).
 * NOT VERIFIED — cannot run in this environment (npm registry 403).
 *
 * To run locally:
 *   npm install --save-dev vitest @vitest/ui jsdom
 *   # Add to vite.config.ts: test: { environment: 'jsdom' }
 *   npx vitest run src/__tests__/api.test.ts
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// We test the module in isolation by mocking globalThis.fetch.
// The module uses sessionStorage which jsdom provides.

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeSession(accessToken = 'access-1', refreshToken = 'refresh-1') {
  return {
    access_token: accessToken,
    refresh_token: refreshToken,
    user: { id: 'u1', email: 'test@example.com', role: 'participant', username: 'test', display_name: 'Test' },
  };
}

function seedSession(accessToken = 'access-1', refreshToken = 'refresh-1') {
  sessionStorage.setItem('tickvendor.session', JSON.stringify(makeSession(accessToken, refreshToken)));
}

function clearSession() {
  sessionStorage.removeItem('tickvendor.session');
}

function mockFetch(responses: Array<{ status: number; body?: unknown; ok?: boolean }>) {
  let call = 0;
  return vi.fn().mockImplementation(() => {
    const r = responses[call++] ?? responses[responses.length - 1];
    const ok = r.ok ?? r.status < 400;
    return Promise.resolve({
      status: r.status,
      ok,
      headers: { get: (h: string) => h === 'content-type' ? 'application/json' : null },
      json: () => Promise.resolve(r.body ?? {}),
    });
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('apiJson — refresh-on-401', () => {
  beforeEach(() => {
    clearSession();
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    clearSession();
  });

  it('returns data directly when first request succeeds (200)', async () => {
    seedSession();
    const fetchMock = mockFetch([{ status: 200, body: { hello: 'world' } }]);
    globalThis.fetch = fetchMock;

    const { apiJson } = await import('../api');
    const result = await apiJson<{ hello: string }>('some/path');
    expect(result.hello).toBe('world');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('retries exactly once after 401 with refreshed token', async () => {
    seedSession('old-access', 'valid-refresh');
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        // First call: original request → 401
        status: 401, ok: false,
        headers: { get: () => 'application/json' },
        json: () => Promise.resolve({ detail: 'Unauthorized' }),
      })
      .mockResolvedValueOnce({
        // Second call: refresh endpoint → 200 with new tokens
        status: 200, ok: true,
        headers: { get: () => 'application/json' },
        json: () => Promise.resolve({
          access_token: 'new-access',
          refresh_token: 'new-refresh',
          user: { id: 'u1', email: 'test@example.com', role: 'participant', username: 'test', display_name: 'Test' },
        }),
      })
      .mockResolvedValueOnce({
        // Third call: retry of original request with new token → 200
        status: 200, ok: true,
        headers: { get: () => 'application/json' },
        json: () => Promise.resolve({ data: 'success' }),
      });
    globalThis.fetch = fetchMock;

    const { apiJson } = await import('../api');
    const result = await apiJson<{ data: string }>('protected/resource');
    expect(result.data).toBe('success');
    // 3 calls: original + refresh + retry
    expect(fetchMock).toHaveBeenCalledTimes(3);
    // Verify the retry used the new token.
    const retryCall = fetchMock.mock.calls[2];
    const retryHeaders = retryCall[1]?.headers;
    expect(retryHeaders?.get?.('Authorization') ?? retryHeaders?.Authorization).toContain('new-access');
  });

  it('does NOT retry a second time if retry also returns 401', async () => {
    seedSession('old-access', 'valid-refresh');
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ status: 401, ok: false, headers: { get: () => 'application/json' }, json: () => Promise.resolve({}) })
      .mockResolvedValueOnce({ status: 200, ok: true, headers: { get: () => 'application/json' }, json: () => Promise.resolve({ access_token: 'new-access', refresh_token: 'new-refresh', user: {} }) })
      .mockResolvedValueOnce({ status: 401, ok: false, headers: { get: () => 'application/json' }, json: () => Promise.resolve({ detail: 'Still unauthorized' }) });
    globalThis.fetch = fetchMock;

    const { apiJson, ApiError } = await import('../api');
    await expect(apiJson('protected/resource')).rejects.toThrow(ApiError);
    // Exactly 3 calls: original + refresh + one retry (no further retries).
    expect(fetchMock).toHaveBeenCalledTimes(3);
    // Session should be cleared after failed retry.
    expect(sessionStorage.getItem('tickvendor.session')).toBeNull();
  });

  it('concurrent requests share a single refresh promise (dedup)', async () => {
    seedSession('old-access', 'valid-refresh');
    let refreshCallCount = 0;
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('auth/refresh')) {
        refreshCallCount++;
        return Promise.resolve({
          status: 200, ok: true,
          headers: { get: () => 'application/json' },
          json: () => Promise.resolve({ access_token: 'new-access', refresh_token: 'new-refresh', user: {} }),
        });
      }
      // All other requests return 401 first, then 200.
      return Promise.resolve({
        status: 401, ok: false,
        headers: { get: () => 'application/json' },
        json: () => Promise.resolve({}),
      });
    });
    globalThis.fetch = fetchMock;

    const { apiJson } = await import('../api');
    // Fire 3 concurrent requests that all get 401.
    // They should share one refresh call, not trigger 3 separate refreshes.
    // (Note: after refresh, retries will also get 401 in this mock, so they'll throw.)
    const results = await Promise.allSettled([
      apiJson('resource/1'),
      apiJson('resource/2'),
      apiJson('resource/3'),
    ]);
    // All should fail (retry also 401 in this mock), but only ONE refresh should have been made.
    expect(refreshCallCount).toBe(1);
    results.forEach(r => expect(r.status).toBe('rejected'));
  });

  it('clears session when refresh endpoint returns 401', async () => {
    seedSession('old-access', 'invalid-refresh');
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ status: 401, ok: false, headers: { get: () => 'application/json' }, json: () => Promise.resolve({}) })
      .mockResolvedValueOnce({ status: 401, ok: false, headers: { get: () => 'application/json' }, json: () => Promise.resolve({}) });
    globalThis.fetch = fetchMock;

    const { apiJson, ApiError } = await import('../api');
    await expect(apiJson('protected/resource')).rejects.toThrow(ApiError);
    // Session must be cleared after failed refresh.
    expect(sessionStorage.getItem('tickvendor.session')).toBeNull();
  });

  it('does NOT retry FormData body (prevents double-consumption)', async () => {
    seedSession();
    const fetchMock = vi.fn().mockResolvedValue({
      status: 401, ok: false,
      headers: { get: () => 'application/json' },
      json: () => Promise.resolve({}),
    });
    globalThis.fetch = fetchMock;

    const { apiJson, ApiError } = await import('../api');
    const formData = new FormData();
    formData.append('file', new Blob(['data']), 'test.jpg');

    await expect(apiJson('upload/endpoint', { method: 'POST', body: formData })).rejects.toThrow(ApiError);
    // Only 1 fetch call — no refresh attempt, no retry for FormData.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('does NOT attempt refresh for auth/login endpoint', async () => {
    seedSession();
    const fetchMock = vi.fn().mockResolvedValue({
      status: 401, ok: false,
      headers: { get: () => 'application/json' },
      json: () => Promise.resolve({ detail: 'Invalid credentials' }),
    });
    globalThis.fetch = fetchMock;

    const { apiJson, ApiError } = await import('../api');
    await expect(apiJson('auth/login', { method: 'POST', body: JSON.stringify({ email: 'x', password: 'y' }) })).rejects.toThrow(ApiError);
    // Only 1 call — no refresh for auth endpoints.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('does NOT attempt refresh for auth/refresh endpoint', async () => {
    seedSession();
    const fetchMock = vi.fn().mockResolvedValue({
      status: 401, ok: false,
      headers: { get: () => 'application/json' },
      json: () => Promise.resolve({ detail: 'Invalid refresh token' }),
    });
    globalThis.fetch = fetchMock;

    const { apiJson, ApiError } = await import('../api');
    await expect(apiJson('auth/refresh', { method: 'POST', body: JSON.stringify({ refresh_token: 'bad' }) })).rejects.toThrow(ApiError);
    // Only 1 call — no recursive refresh.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
