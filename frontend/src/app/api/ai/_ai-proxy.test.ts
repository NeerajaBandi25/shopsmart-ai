/** @jest-environment node */

import { proxyAiRequest } from '../_ai-proxy';

describe('AI backend proxy', () => {
  const originalBackendUrl = process.env.API_INTERNAL_URL;
  const originalFetch = global.fetch;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    process.env.API_INTERNAL_URL = 'http://backend.test/api/v1';
    global.fetch = jest.fn();
    fetchMock = global.fetch as jest.Mock;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalBackendUrl === undefined) delete process.env.API_INTERNAL_URL;
    else process.env.API_INTERNAL_URL = originalBackendUrl;
    jest.restoreAllMocks();
  });

  it('reports missing backend configuration as an internal error', async () => {
    delete process.env.API_INTERNAL_URL;

    const response = await proxyAiRequest(
      new Request('http://localhost/api/ai/conversations'),
      '/ai/conversations',
      { method: 'GET' }
    );

    expect(response.status).toBe(500);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('reports transport failure as service unavailable', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('private transport detail'));
    const log = jest.spyOn(console, 'error').mockImplementation(() => undefined);

    const response = await proxyAiRequest(
      new Request('http://localhost/api/ai/conversations'),
      '/ai/conversations',
      { method: 'GET' }
    );

    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({
      error_code: 'ai_service_unavailable',
      status_code: 503,
    });
    expect(log).toHaveBeenCalledWith('ai_backend_transport_error', {
      endpoint: '/ai/conversations',
      method: 'GET',
      error_type: 'TypeError',
    });
  });

  it('preserves backend error statuses and bodies', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error_code: 'invalid_input' }), { status: 422 })
    );

    const response = await proxyAiRequest(
      new Request('http://localhost/api/ai/chat', { method: 'POST' }),
      '/ai/chat',
      { method: 'POST' }
    );

    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({ error_code: 'invalid_input' });
  });
});
