import {
  changePassword,
  getCsrfToken,
  getProduct,
  getProducts,
  getProfile,
  login,
  logout,
  register,
} from './api-client';
import { useCommerceStore } from './commerce-store';

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

  it('clears private commerce state after logout succeeds', async () => {
    useCommerceStore.getState().syncCartCount({ items: [{ quantity: 3 }] });
    mockedFetch
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'csrf-token' }, 200))
      .mockResolvedValueOnce(jsonResponse(undefined, 204));

    await logout();

    expect(useCommerceStore.getState().cartItemCount).toBe(0);
  });

  it('clears private commerce state when logout discovers an invalid session', async () => {
    useCommerceStore.getState().syncCartCount({ items: [{ quantity: 3 }] });
    mockedFetch
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'csrf-token' }, 200))
      .mockResolvedValueOnce(jsonResponse({ detail: 'Unauthorized' }, 401));

    await expect(logout()).rejects.toThrow('Unauthorized');

    expect(useCommerceStore.getState().cartItemCount).toBe(0);
  });

  it('includes credentials: include', async () => {
    mockedFetch
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'csrf-token' }, 200))
      .mockResolvedValueOnce(jsonResponse(undefined, 204));
    await logout();
    expect(mockedFetch).toHaveBeenNthCalledWith(
      2,
      '/api/auth/logout',
      expect.objectContaining({
        credentials: 'include',
        headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-token' }),
      })
    );
  });
});

describe('same-origin authentication API routes', () => {
  const originalPublicApiUrl = process.env.NEXT_PUBLIC_API_URL;

  beforeEach(() => {
    mockedFetch.mockReset();
    process.env.NEXT_PUBLIC_API_URL = 'https://backend.example.test/api/v1';
  });

  it('loads the product catalog through the same-origin BFF', async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse({ items: [], skip: 24, limit: 24, total: 0 }, 200)
    );

    await expect(getProducts(24, 24)).resolves.toEqual({
      items: [],
      skip: 24,
      limit: 24,
      total: 0,
    });

    expect(mockedFetch).toHaveBeenCalledWith(
      '/api/products?skip=24&limit=24',
      expect.objectContaining({ credentials: 'include' })
    );
    expect(mockedFetch.mock.calls[0][0]).not.toContain('backend.example.test');
  });

  it('serializes catalog filters and fetches product details through the same-origin BFF', async () => {
    mockedFetch
      .mockResolvedValueOnce(jsonResponse({ items: [], skip: 0, limit: 24, total: 0 }, 200))
      .mockResolvedValueOnce(jsonResponse({ id: 'product-1', name: 'Northstar 14' }, 200));

    await getProducts(0, 24, {
      q: 'laptop',
      category: 'laptops',
      max_price_minor: 6000000,
      in_stock_only: true,
      sort: 'price_asc',
    });
    await getProduct('product-1');

    expect(mockedFetch).toHaveBeenNthCalledWith(
      1,
      '/api/products?skip=0&limit=24&q=laptop&category=laptops&max_price_minor=6000000&in_stock_only=true&sort=price_asc',
      expect.objectContaining({ credentials: 'include' })
    );
    expect(mockedFetch).toHaveBeenNthCalledWith(
      2,
      '/api/products/product-1',
      expect.objectContaining({ credentials: 'include' })
    );
  });

  afterAll(() => {
    if (originalPublicApiUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = originalPublicApiUrl;
  });

  it('sends registration and login to same-origin BFF paths with credentials and JSON bodies', async () => {
    useCommerceStore.getState().syncCartCount({ items: [{ quantity: 2 }] });
    mockedFetch
      .mockResolvedValueOnce(
        jsonResponse({ user_id: 'user-1', email: 'a@example.com', created_at: 'now' }, 201)
      )
      .mockResolvedValueOnce(jsonResponse({ user_id: 'user-1', email: 'a@example.com' }, 200));

    await register('a@example.com', 'Secret123!');
    await login('a@example.com', 'Secret123!');

    expect(useCommerceStore.getState().cartItemCount).toBe(0);

    expect(mockedFetch).toHaveBeenNthCalledWith(
      1,
      '/api/auth/register',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ email: 'a@example.com', password: 'Secret123!' }),
      })
    );
    expect(mockedFetch).toHaveBeenNthCalledWith(
      2,
      '/api/auth/login',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ email: 'a@example.com', password: 'Secret123!' }),
      })
    );
    expect(
      mockedFetch.mock.calls.every(
        ([url]) => url === '/api/auth/register' || url === '/api/auth/login'
      )
    ).toBe(true);
  });

  it('loads the current user and CSRF token through same-origin routes with credentials', async () => {
    mockedFetch
      .mockResolvedValueOnce(
        jsonResponse({ user_id: 'user-1', email: 'a@example.com', created_at: 'now' }, 200)
      )
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'csrf-token' }, 200));

    await expect(getProfile()).resolves.toEqual({
      user_id: 'user-1',
      email: 'a@example.com',
      created_at: 'now',
    });
    await expect(getCsrfToken()).resolves.toBe('csrf-token');

    expect(mockedFetch).toHaveBeenNthCalledWith(
      1,
      '/api/auth/me',
      expect.objectContaining({
        method: 'GET',
        credentials: 'include',
      })
    );
    expect(mockedFetch).toHaveBeenNthCalledWith(
      2,
      '/api/auth/csrf',
      expect.objectContaining({
        method: 'GET',
        credentials: 'include',
      })
    );
  });

  it('clears private commerce state when profile validation returns 401', async () => {
    useCommerceStore.getState().syncCartCount({ items: [{ quantity: 2 }] });
    mockedFetch.mockResolvedValueOnce(jsonResponse({ detail: 'Unauthorized' }, 401));

    await expect(getProfile()).rejects.toThrow('Unauthorized');

    expect(useCommerceStore.getState().cartItemCount).toBe(0);
  });

  it('posts logout and password change with the CSRF header and same-origin credentials', async () => {
    mockedFetch
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'csrf-token' }, 200))
      .mockResolvedValueOnce(jsonResponse(undefined, 204))
      .mockResolvedValueOnce(jsonResponse(undefined, 204));

    await logout();
    await changePassword('OldSecret123!', 'NewSecret123!', 'provided-token');

    expect(mockedFetch).toHaveBeenNthCalledWith(
      2,
      '/api/auth/logout',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-token' }),
      })
    );
    expect(mockedFetch).toHaveBeenNthCalledWith(
      3,
      '/api/auth/password',
      expect.objectContaining({
        method: 'PUT',
        credentials: 'include',
        headers: expect.objectContaining({ 'X-CSRF-Token': 'provided-token' }),
        body: JSON.stringify({ current_password: 'OldSecret123!', new_password: 'NewSecret123!' }),
      })
    );
  });

  it('fetches a same-origin CSRF token before password change when none is supplied', async () => {
    mockedFetch
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'csrf-token' }, 200))
      .mockResolvedValueOnce(jsonResponse(undefined, 204));

    await changePassword('OldSecret123!', 'NewSecret123!');

    expect(mockedFetch).toHaveBeenNthCalledWith(
      1,
      '/api/auth/csrf',
      expect.objectContaining({
        method: 'GET',
        credentials: 'include',
      })
    );
    expect(mockedFetch).toHaveBeenNthCalledWith(
      2,
      '/api/auth/password',
      expect.objectContaining({
        method: 'PUT',
        credentials: 'include',
        headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-token' }),
      })
    );
  });

  it('clears private commerce state after password change succeeds', async () => {
    useCommerceStore.getState().syncCartCount({ items: [{ quantity: 2 }] });
    mockedFetch.mockResolvedValueOnce(jsonResponse(undefined, 204));

    await changePassword('OldSecret123!', 'NewSecret123!', 'provided-token');

    expect(useCommerceStore.getState().cartItemCount).toBe(0);
  });

  it('clears private commerce state when password change reports an invalid session', async () => {
    useCommerceStore.getState().syncCartCount({ items: [{ quantity: 2 }] });
    mockedFetch.mockResolvedValueOnce(jsonResponse({ detail: 'Unauthorized' }, 401));

    await expect(
      changePassword('OldSecret123!', 'NewSecret123!', 'provided-token')
    ).rejects.toThrow('Unauthorized');

    expect(useCommerceStore.getState().cartItemCount).toBe(0);
  });

  it('preserves login error messages and status handling for existing callers', async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse(
        {
          detail: 'Too many login attempts',
          error_code: 'rate_limited',
          status_code: 429,
        },
        429
      )
    );

    await expect(login('a@example.com', 'wrong')).rejects.toThrow('Too many login attempts');
    expect(mockedFetch).toHaveBeenCalledWith('/api/auth/login', expect.any(Object));
  });
});
