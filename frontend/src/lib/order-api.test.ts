import { checkoutOrder, getOrder, getOrders, retryPayment } from './order-api';
import { useCommerceStore } from './commerce-store';

const mockedFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockedFetch;

const jsonResponse = (body: unknown, status = 200): Response =>
  ({ ok: status >= 200 && status < 300, status, json: async () => body }) as Response;

describe('same-origin order API routes', () => {
  const originalPublicUrl = process.env.NEXT_PUBLIC_API_URL;

  beforeEach(() => {
    mockedFetch.mockReset();
    useCommerceStore.getState().clearPrivateCommerce();
    process.env.NEXT_PUBLIC_API_URL = 'https://backend.invalid/api/v1';
  });

  afterAll(() => {
    if (originalPublicUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = originalPublicUrl;
  });

  it('submits checkout through the same-origin BFF with credentials, CSRF, and idempotency key', async () => {
    const items = [{ product_id: 'product-1', quantity: 2 }];
    const deliveryAddress = {
      recipient_name: 'Portfolio Shopper',
      phone: '+91 98765 43210',
      address_line1: '12 Example Road',
      address_line2: null,
      city: 'Bengaluru',
      region: 'Karnataka',
      postal_code: '560001',
      country_code: 'IN' as const,
    };
    mockedFetch
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'checkout-csrf' }))
      .mockResolvedValueOnce(jsonResponse({ id: 'order-1', items }, 201));

    await expect(checkoutOrder(items, 'stable-key-1', undefined, deliveryAddress)).resolves.toEqual(
      { id: 'order-1', items }
    );

    expect(mockedFetch.mock.calls[0][0]).toBe('/api/auth/csrf');
    expect(mockedFetch.mock.calls[1][0]).toBe('/api/orders/checkout');
    expect(mockedFetch.mock.calls[1][1]).toEqual(
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ items, delivery_address: deliveryAddress }),
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

  it('loads one normalized payment state through the same-origin order route', async () => {
    const order = { id: '00000000-0000-4000-8000-000000000001', payment_status: 'succeeded' };
    mockedFetch.mockResolvedValueOnce(jsonResponse(order));

    await expect(getOrder(order.id)).resolves.toEqual(order);

    expect(mockedFetch).toHaveBeenCalledWith(
      `/api/orders/${order.id}`,
      expect.objectContaining({ credentials: 'include', cache: 'no-store' })
    );
  });

  it('retries payment on the existing order through the same-origin CSRF protected route', async () => {
    const orderId = '00000000-0000-4000-8000-000000000001';
    const order = { id: orderId, payment_status: 'requires_action' };
    mockedFetch
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'retry-csrf' }))
      .mockResolvedValueOnce(jsonResponse(order));

    await expect(retryPayment(orderId)).resolves.toEqual(order);

    expect(mockedFetch.mock.calls[0][0]).toBe('/api/auth/csrf');
    expect(mockedFetch.mock.calls[1][0]).toBe(`/api/orders/${orderId}/payment/retry`);
    expect(mockedFetch.mock.calls[1][1]).toEqual(
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRF-Token': 'retry-csrf' },
      })
    );
  });

  it('clears private commerce state when an order response reports an invalid session', async () => {
    useCommerceStore.getState().syncCartCount({ items: [{ quantity: 2 }] });
    mockedFetch.mockResolvedValueOnce(jsonResponse({ detail: 'Unauthorized' }, 401));

    await expect(getOrders()).rejects.toThrow('Unauthorized');

    expect(useCommerceStore.getState().cartItemCount).toBe(0);
  });
});
