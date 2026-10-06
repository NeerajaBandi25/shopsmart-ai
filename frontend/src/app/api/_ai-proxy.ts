type AiProxyOptions = {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  forwardBody?: boolean;
  streamResponse?: boolean;
};

export async function proxyAiRequest(
  request: Request,
  endpoint: string,
  options: AiProxyOptions
): Promise<Response> {
  const backendUrl = process.env.API_INTERNAL_URL;
  if (!backendUrl)
    return new Response(JSON.stringify({ detail: 'AI service unavailable' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  const headers = new Headers({
    Accept: options.streamResponse ? 'text/event-stream' : 'application/json',
  });
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
      signal: request.signal,
    });
    const responseHeaders = new Headers({ 'Cache-Control': 'no-store' });
    const upstreamType = upstream.headers.get('content-type');
    if (upstreamType) responseHeaders.set('Content-Type', upstreamType);
    const requestId = upstream.headers.get('x-request-id');
    if (requestId) responseHeaders.set('X-Request-ID', requestId);
    // Pass the upstream stream through unchanged so SSE frames arrive progressively.
    const body = [204, 205, 304].includes(upstream.status)
      ? null
      : options.streamResponse
        ? upstream.body
        : await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error('ai_backend_transport_error', {
      endpoint,
      method: options.method,
      error_type: error instanceof Error ? error.name : 'UnknownError',
    });
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
