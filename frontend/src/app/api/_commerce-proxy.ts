import { getSetCookieHeaders } from './auth/_proxy';

type CommerceProxyOptions = {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  forwardCookie?: boolean;
  forwardCsrfToken?: boolean;
  forwardIdempotencyKey?: boolean;
  forwardBody?: boolean;
  query?: string;
};

const SERVICE_UNAVAILABLE_BODY = JSON.stringify({
  detail: 'Commerce service unavailable',
  error_code: 'commerce_service_unavailable',
  status_code: 503,
});

function serviceUnavailable(): Response {
  return new Response(SERVICE_UNAVAILABLE_BODY, {
    status: 503,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

export async function proxyCommerceRequest(
  request: Request,
  endpoint: string,
  options: CommerceProxyOptions
): Promise<Response> {
  const backendUrl = process.env.API_INTERNAL_URL;
  if (!backendUrl) return serviceUnavailable();

  const headers = new Headers({ Accept: 'application/json' });
  const contentType = request.headers.get('content-type');
  if (options.forwardBody && contentType) headers.set('Content-Type', contentType);

  if (options.forwardCookie) {
    const cookie = request.headers.get('cookie');
    if (cookie) headers.set('Cookie', cookie);
  }
  if (options.forwardCsrfToken) {
    const csrfToken = request.headers.get('x-csrf-token');
    if (csrfToken) headers.set('X-CSRF-Token', csrfToken);
  }
  if (options.forwardIdempotencyKey) {
    const idempotencyKey = request.headers.get('idempotency-key');
    if (idempotencyKey) headers.set('Idempotency-Key', idempotencyKey);
  }

  const body = options.forwardBody ? await request.text() : undefined;
  const query = options.query ? `?${options.query}` : '';

  try {
    const upstream = await fetch(`${backendUrl.replace(/\/$/, '')}${endpoint}${query}`, {
      method: options.method,
      headers,
      body,
      cache: 'no-store',
      redirect: 'manual',
    });

    const responseHeaders = new Headers({ 'Cache-Control': 'no-store' });
    const contentTypeHeader = upstream.headers.get('content-type');
    if (contentTypeHeader) responseHeaders.set('Content-Type', contentTypeHeader);

    for (const header of [
      'retry-after',
      'x-request-id',
      'x-ratelimit-limit',
      'x-ratelimit-remaining',
      'x-ratelimit-reset',
    ]) {
      const value = upstream.headers.get(header);
      if (value) responseHeaders.set(header, value);
    }
    for (const cookie of getSetCookieHeaders(upstream.headers)) {
      responseHeaders.append('Set-Cookie', cookie);
    }

    const responseBody = [204, 205, 304].includes(upstream.status) ? null : await upstream.text();
    return new Response(responseBody, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return serviceUnavailable();
  }
}
