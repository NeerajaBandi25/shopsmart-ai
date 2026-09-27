/** @jest-environment node */

import { NextRequest } from 'next/server';
import { middleware } from './middleware';

const mockedFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockedFetch;

function makeRequest(path: string, cookie?: string): NextRequest {
  const headers = new Headers();
  if (cookie) headers.set('Cookie', cookie);
  return new NextRequest(new URL(path, 'https://shopsmart.test'), { headers });
}

function response(status: number, body = '', headers = new Headers()): Response {
  return new Response(body || null, { status, headers });
}

describe('authentication middleware', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    process.env.API_INTERNAL_URL = 'http://backend:8000/api/v1';
    process.env.NEXT_PUBLIC_API_URL = 'http://public-backend.invalid/api/v1';
  });

  it('validates a protected page through the same-origin BFF, forwards Cookie, and relays refresh cookies', async () => {
    const headers = new Headers({ 'Content-Type': 'application/json' });
    headers.append(
      'Set-Cookie',
      'session_id=refreshed; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=2592000'
    );
    mockedFetch.mockResolvedValueOnce(response(200, '{"user_id":"u1"}', headers));

    const result = await middleware(makeRequest('/account?tab=profile', 'session_id=active'));

    expect(String(mockedFetch.mock.calls[0][0])).toBe('https://shopsmart.test/api/auth/me');
    expect(mockedFetch.mock.calls[0][1]).toEqual(
      expect.objectContaining({ method: 'GET', cache: 'no-store', redirect: 'manual' })
    );
    const fetchHeaders = new Headers(mockedFetch.mock.calls[0][1]?.headers);
    expect(fetchHeaders.get('cookie')).toBe('session_id=active');
    expect(mockedFetch.mock.calls[0][0]).not.toContain('public-backend.invalid');
    expect(result.headers.get('x-middleware-next')).toBe('1');
    expect(result.headers.get('set-cookie')).toContain(
      'session_id=refreshed; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=2592000'
    );
  });

  it('redirects a protected request with no session only when the BFF returns 401', async () => {
    mockedFetch.mockResolvedValueOnce(response(401, '{"detail":"Unauthorized"}'));

    const result = await middleware(makeRequest('/account'));

    const fetchHeaders = new Headers(mockedFetch.mock.calls[0][1]?.headers);
    expect(fetchHeaders.has('cookie')).toBe(false);
    expect(result.status).toBe(307);
    const location = new URL(result.headers.get('location')!);
    expect(location.origin).toBe('https://shopsmart.test');
    expect(location.pathname).toBe('/auth/login');
    expect(location.searchParams.get('redirectTo')).toBe('/account');
  });

  it('redirects after logout when the BFF reports the session was invalidated', async () => {
    mockedFetch.mockResolvedValueOnce(response(401, '{"detail":"Session invalidated"}'));

    const result = await middleware(makeRequest('/orders', 'session_id=revoked'));

    expect(result.status).toBe(307);
    expect(new URL(result.headers.get('location')!).searchParams.get('redirectTo')).toBe('/orders');
  });

  it.each([403, 429, 503])('does not redirect for upstream %i responses', async (status) => {
    const error = JSON.stringify({ detail: 'Authentication check failed', status_code: status });
    mockedFetch.mockResolvedValueOnce(
      response(status, error, new Headers({ 'Content-Type': 'application/json' }))
    );

    const result = await middleware(makeRequest('/dashboard', 'session_id=active'));

    expect(result.status).toBe(status);
    expect(result.headers.get('location')).toBeNull();
    expect(await result.json()).toEqual(JSON.parse(error));
  });

  it('returns a service failure instead of redirecting when the BFF is unavailable', async () => {
    mockedFetch.mockRejectedValueOnce(new Error('connection refused'));

    const result = await middleware(makeRequest('/dashboard', 'session_id=active'));

    expect(result.status).toBe(503);
    expect(result.headers.get('location')).toBeNull();
    expect(await result.json()).toEqual({
      detail: 'Authentication service unavailable',
      error_code: 'auth_service_unavailable',
      status_code: 503,
    });
  });

  it('ignores an external redirectTo query and keeps the redirect target local', async () => {
    mockedFetch.mockResolvedValueOnce(response(401));

    const result = await middleware(makeRequest('/account?redirectTo=https://evil.example/steal'));

    const location = new URL(result.headers.get('location')!);
    expect(location.origin).toBe('https://shopsmart.test');
    expect(location.pathname).toBe('/auth/login');
    expect(location.searchParams.get('redirectTo')).toBe('/account');
  });

  it.each(['/', '/auth/login', '/auth/register', '/api/auth/me'])(
    'preserves anonymous/public navigation at %s without a session probe',
    async (path) => {
      const result = await middleware(makeRequest(path));

      expect(result.headers.get('x-middleware-next')).toBe('1');
      expect(mockedFetch).not.toHaveBeenCalled();
    }
  );
});
