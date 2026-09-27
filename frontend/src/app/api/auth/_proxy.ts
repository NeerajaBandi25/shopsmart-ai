type ProxyOptions = {
  method: 'GET' | 'POST' | 'PUT';
  forwardCookie?: boolean;
  forwardCsrfToken?: boolean;
  forwardBody?: boolean;
};

const SERVICE_UNAVAILABLE_BODY = JSON.stringify({
  detail: 'Authentication service unavailable',
  error_code: 'auth_service_unavailable',
  status_code: 503,
});

function splitSetCookieHeader(value: string): string[] {
  return value
    .split(/,(?=\s*[^=;,\s]+=)/)
    .map((cookie) => cookie.trim())
    .filter(Boolean);
}

export function getSetCookieHeaders(headers: Headers): string[] {
  const headersWithGetSetCookie = headers as Headers & {
    getSetCookie?: () => string[];
  };

  if (typeof headersWithGetSetCookie.getSetCookie === 'function') {
    return headersWithGetSetCookie.getSetCookie();
  }

  const combined = headers.get('set-cookie');
  return combined ? splitSetCookieHeader(combined) : [];
}

function serviceUnavailable(): Response {
  return new Response(SERVICE_UNAVAILABLE_BODY, {
    status: 503,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

export async function proxyAuthRequest(
  request: Request,
  endpoint: string,
  options: ProxyOptions
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

  let body: string | undefined;
  if (options.forwardBody) body = await request.text();

  try {
    const upstream = await fetch(`${backendUrl.replace(/\/$/, '')}${endpoint}`, {
      method: options.method,
      headers,
      body,
      cache: 'no-store',
      redirect: 'manual',
    });

    const responseHeaders = new Headers({ 'Cache-Control': 'no-store' });
    const upstreamContentType = upstream.headers.get('content-type');
    if (upstreamContentType) responseHeaders.set('Content-Type', upstreamContentType);

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
