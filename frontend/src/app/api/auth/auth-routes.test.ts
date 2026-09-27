/** @jest-environment node */

import { GET as getCsrf } from './csrf/route';
import { POST as login } from './login/route';
import { POST as logout } from './logout/route';
import { GET as getMe } from './me/route';
import { PUT as changePassword } from './password/route';
import { POST as register } from './register/route';

const mockedFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockedFetch;

function upstreamResponse(
  body: string,
  status = 200,
  headers = new Headers({ 'Content-Type': 'application/json' })
): Response {
  return new Response(body || null, { status, headers });
}

function request(url: string, method: string, body?: string, headers?: HeadersInit): Request {
  return new Request(url, { method, body, headers });
}

function forwardedHeaders(callIndex: number): Headers {
  return new Headers(mockedFetch.mock.calls[callIndex][1]?.headers);
}

describe('authentication BFF routes', () => {
  const originalInternalUrl = process.env.API_INTERNAL_URL;
  const originalPublicUrl = process.env.NEXT_PUBLIC_API_URL;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env.API_INTERNAL_URL = 'http://backend:8000/api/v1/';
    process.env.NEXT_PUBLIC_API_URL = 'http://public-backend.invalid/api/v1';
  });

  afterAll(() => {
    if (originalInternalUrl === undefined) delete process.env.API_INTERNAL_URL;
    else process.env.API_INTERNAL_URL = originalInternalUrl;
    if (originalPublicUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = originalPublicUrl;
  });

  it('maps registration and login to backend auth routes and uses only the server URL', async () => {
    mockedFetch
      .mockResolvedValueOnce(upstreamResponse('{"user_id":"u1"}', 201))
      .mockResolvedValueOnce(upstreamResponse('{"user_id":"u1"}', 200));

    await register(
      request(
        'http://localhost/api/auth/register',
        'POST',
        '{"email":"a@example.com","password":"Secret123!"}',
        { 'Content-Type': 'application/json' }
      )
    );
    await login(
      request(
        'http://localhost/api/auth/login',
        'POST',
        '{"email":"a@example.com","password":"Secret123!"}',
        { 'Content-Type': 'application/json' }
      )
    );

    expect(mockedFetch.mock.calls[0][0]).toBe('http://backend:8000/api/v1/auth/register');
    expect(mockedFetch.mock.calls[1][0]).toBe('http://backend:8000/api/v1/auth/login');
    expect(mockedFetch.mock.calls[0][0]).not.toContain('public-backend.invalid');
    expect(mockedFetch.mock.calls[0][1]).toEqual(
      expect.objectContaining({
        method: 'POST',
        body: '{"email":"a@example.com","password":"Secret123!"}',
      })
    );
  });

  it('forwards cookies to current-user and CSRF endpoints and relays refreshed session cookies', async () => {
    const headers = new Headers({ 'Content-Type': 'application/json' });
    headers.append(
      'Set-Cookie',
      'session_id=rotated; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=2592000'
    );
    headers.append(
      'Set-Cookie',
      'csrf_hint=rotated; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Secure'
    );
    mockedFetch
      .mockResolvedValueOnce(upstreamResponse('{"user_id":"u1"}', 200, headers))
      .mockResolvedValueOnce(upstreamResponse('{"csrf_token":"token"}'));

    const me = await getMe(
      request('http://localhost/api/auth/me', 'GET', undefined, { Cookie: 'session_id=old' })
    );
    const csrf = await getCsrf(
      request('http://localhost/api/auth/csrf', 'GET', undefined, { Cookie: 'session_id=old' })
    );

    expect(forwardedHeaders(0).get('cookie')).toBe('session_id=old');
    expect(forwardedHeaders(1).get('cookie')).toBe('session_id=old');
    expect(me.headers.get('set-cookie')).toContain(
      'session_id=rotated; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=2592000'
    );
    const relayedCookies = (
      me.headers as Headers & { getSetCookie?: () => string[] }
    ).getSetCookie?.() ?? [me.headers.get('set-cookie') ?? ''];
    expect(relayedCookies).toHaveLength(2);
    expect(relayedCookies[1]).toContain('Expires=Thu, 01 Jan 1970 00:00:00 GMT');
    expect(await csrf.json()).toEqual({ csrf_token: 'token' });
  });

  it('maps logout to the backend and forwards its cookie and CSRF token', async () => {
    const headers = new Headers({ 'Content-Type': 'application/json' });
    headers.append(
      'Set-Cookie',
      'session_id=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; HttpOnly; Secure; SameSite=Strict'
    );
    mockedFetch.mockResolvedValueOnce(upstreamResponse('', 204, headers));

    const response = await logout(
      request('http://localhost/api/auth/logout', 'POST', undefined, {
        Cookie: 'session_id=active',
        'X-CSRF-Token': 'logout-token',
      })
    );

    expect(mockedFetch).toHaveBeenCalledWith(
      'http://backend:8000/api/v1/auth/logout',
      expect.objectContaining({ method: 'POST' })
    );
    expect(forwardedHeaders(0).get('cookie')).toBe('session_id=active');
    expect(forwardedHeaders(0).get('x-csrf-token')).toBe('logout-token');
    expect(response.status).toBe(204);
    expect(response.headers.get('set-cookie')).toContain(
      'Max-Age=0; HttpOnly; Secure; SameSite=Strict'
    );
    expect(response.headers.get('set-cookie')).toContain('Expires=Thu, 01 Jan 1970 00:00:00 GMT');
  });

  it('maps password change to /users/password and forwards JSON, Cookie, and CSRF token', async () => {
    mockedFetch.mockResolvedValueOnce(upstreamResponse('', 204));

    const response = await changePassword(
      request(
        'http://localhost/api/auth/password',
        'PUT',
        '{"current_password":"old","new_password":"NewSecret123!"}',
        {
          'Content-Type': 'application/json',
          Cookie: 'session_id=active',
          'X-CSRF-Token': 'password-token',
        }
      )
    );

    expect(mockedFetch).toHaveBeenCalledWith(
      'http://backend:8000/api/v1/users/password',
      expect.objectContaining({
        method: 'PUT',
        body: '{"current_password":"old","new_password":"NewSecret123!"}',
      })
    );
    expect(forwardedHeaders(0).get('cookie')).toBe('session_id=active');
    expect(forwardedHeaders(0).get('x-csrf-token')).toBe('password-token');
    expect(response.status).toBe(204);
  });

  it.each([401, 403, 429])('preserves backend status and error envelope for %i', async (status) => {
    const errorBody = JSON.stringify({
      detail: 'Backend auth error',
      error_code: 'auth_error',
      status_code: status,
    });
    mockedFetch.mockResolvedValueOnce(upstreamResponse(errorBody, status));

    const response = await login(
      request('http://localhost/api/auth/login', 'POST', '{}', {
        'Content-Type': 'application/json',
      })
    );

    expect(response.status).toBe(status);
    expect(await response.json()).toEqual(JSON.parse(errorBody));
  });

  it('returns a safe service failure when the backend is unavailable', async () => {
    mockedFetch.mockRejectedValueOnce(new Error('connection refused'));

    const response = await getMe(
      request('http://localhost/api/auth/me', 'GET', undefined, { Cookie: 'session_id=active' })
    );

    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({
      detail: 'Authentication service unavailable',
      error_code: 'auth_service_unavailable',
      status_code: 503,
    });
  });

  it('returns a service failure without falling back to NEXT_PUBLIC_API_URL', async () => {
    delete process.env.API_INTERNAL_URL;

    const response = await getMe(request('http://localhost/api/auth/me', 'GET'));

    expect(mockedFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(503);
  });
});
