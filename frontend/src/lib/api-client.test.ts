import { logout } from './api-client';

// Mock fetch
global.fetch = jest.fn();

describe('api-client.logout()', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('throws on 401 response', async () => {
    fetch.mockResolvedValueOnce({ ok: false, status: 401, json: () => Promise.resolve({ detail: 'Unauthorized' }) });
    await expect(logout()).rejects.toThrow('Unauthorized');
  });

  it('resolves on 204 response', async () => {
    fetch.mockResolvedValueOnce({ ok: true, status: 204 });
    await expect(logout()).resolves.toBeUndefined();
  });

  it('includes credentials: include', async () => {
    await logout().catch(() => {}); // Ignore result, just check call
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/auth/logout'),
      expect.objectContaining({ credentials: 'include' })
    );
  });
});