type AiProxyOptions = { method: 'GET' | 'POST'; forwardBody?: boolean };

export async function proxyAiRequest(
  request: Request,
  endpoint: string,
  options: AiProxyOptions
): Promise<Response> {
  const backendUrl = process.env.API_INTERNAL_URL;
  if (!backendUrl)
    return new Response(JSON.stringify({ detail: 'AI service unavailable' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  const headers = new Headers({ Accept: 'application/json' });
  const cookie = request.headers.get('cookie');
  const csrf = request.headers.get('x-csrf-token');
  const contentType = request.headers.get('content-type');
  if (cookie) headers.set('Cookie', cookie);
  if (csrf) headers.set('X-CSRF-Token', csrf);
  if (options.forwardBody && contentType) headers.set('Content-Type', contentType);
  try {
    const upstream = await fetch(`${backendUrl.replace(/\/$/, '')}${endpoint}`, {
      method: options.method,
      headers,
      body: options.forwardBody ? await request.arrayBuffer() : undefined,
      cache: 'no-store',
      redirect: 'manual',
    });
    const responseHeaders = new Headers({ 'Cache-Control': 'no-store' });
    const upstreamType = upstream.headers.get('content-type');
    if (upstreamType) responseHeaders.set('Content-Type', upstreamType);
    const requestId = upstream.headers.get('x-request-id');
    if (requestId) responseHeaders.set('X-Request-ID', requestId);
    return new Response([204, 205, 304].includes(upstream.status) ? null : await upstream.text(), {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return new Response(
      JSON.stringify({
        detail: 'AI service unavailable',
        error_code: 'ai_service_unavailable',
        status_code: 503,
      }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}
