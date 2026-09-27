import { checkoutOrder, getOrders } from './order-api';

const mockedFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockedFetch;

const jsonResponse = (body: unknown, status = 200): Response =>
  ({ ok: status >= 200 && status < 300, status, json: async () => body }) as Response;

describe('same-origin order API routes', () => {
  const originalPublicUrl = process.env.NEXT_PUBLIC_API_URL;

  beforeEach(() => {
    mockedFetch.mockReset();
    process.env.NEXT_PUBLIC_API_URL = 'https://backend.invalid/api/v1';
  });

  afterAll(() => {
    if (originalPublicUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = originalPublicUrl;
  });

  it('submits checkout through the same-origin BFF with credentials, CSRF, and idempotency key', async () => {
    const items = [{ product_id: 'product-1', quantity: 2 }];
    mockedFetch
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'checkout-csrf' }))
      .mockResolvedValueOnce(jsonResponse({ id: 'order-1', items }, 201));

    await expect(checkoutOrder(items, 'stable-key-1')).resolves.toEqual({ id: 'order-1', items });

    expect(mockedFetch.mock.calls[0][0]).toBe('/api/auth/csrf');
    expect(mockedFetch.mock.calls[1][0]).toBe('/api/orders/checkout');
    expect(mockedFetch.mock.calls[1][1]).toEqual(
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ items }),
        headers: expect.objectContaining({
          'X-CSRF-Token': 'checkout-csrf',
          'Idempotency-Key': 'stable-key-1',
        }),
      })
    );
    expect(mockedFetch.mock.calls.every(([url]) => !String(url).includes('backend.invalid'))).toBe(
      true
    );
  });

  it('loads order history from the same-origin route with credentials and no-store caching', async () => {
    mockedFetch.mockResolvedValueOnce(jsonResponse([]));

    await expect(getOrders()).resolves.toEqual([]);

    expect(mockedFetch).toHaveBeenCalledWith(
      '/api/orders',
      expect.objectContaining({ credentials: 'include', cache: 'no-store' })
    );
  });
});
