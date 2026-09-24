import { logout } from './api-client';

// Mock fetch
const mockedFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockedFetch;

const jsonResponse = (body: unknown, status: number): Response =>
  ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }) as Response;

describe('api-client.logout()', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('throws on 401 response', async () => {
    mockedFetch
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'csrf-token' }, 200))
      .mockResolvedValueOnce(jsonResponse({ detail: 'Unauthorized' }, 401));
    await expect(logout()).rejects.toThrow('Unauthorized');
  });

  it('resolves on 204 response', async () => {
    mockedFetch
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'csrf-token' }, 200))
      .mockResolvedValueOnce(jsonResponse(undefined, 204));
    await expect(logout()).resolves.toBeUndefined();
  });

  it('includes credentials: include', async () => {
    mockedFetch
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'csrf-token' }, 200))
      .mockResolvedValueOnce(jsonResponse(undefined, 204));
    await logout();
    expect(mockedFetch).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('/auth/logout'),
      expect.objectContaining({
        credentials: 'include',
        headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-token' }),
      })
    );
  });
});
