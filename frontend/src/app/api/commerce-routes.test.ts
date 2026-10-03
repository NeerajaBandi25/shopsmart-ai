/** @jest-environment node */

import { GET as getProducts } from './products/route';
import { GET as getProduct } from './products/[productId]/route';
import { GET as getCart } from './cart/route';
import { POST as addCartItem } from './cart/items/route';
import {
  DELETE as removeCartItem,
  PUT as setCartItemQuantity,
} from './cart/items/[productId]/route';
import { POST as checkout } from './orders/checkout/route';
import { GET as getOrders } from './orders/route';

const mockedFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockedFetch;

function upstreamResponse(
  body: string,
  status = 200,
  headers = new Headers({ 'Content-Type': 'application/json' })
): Response {
  return new Response(body || null, { status, headers });
}

function request(path: string, method: string, body?: string, headers?: HeadersInit): Request {
  return new Request(`http://localhost${path}`, { method, body, headers });
}

function forwardedHeaders(callIndex = 0): Headers {
  return new Headers(mockedFetch.mock.calls[callIndex][1]?.headers);
}

describe('commerce BFF routes', () => {
  const originalInternalUrl = process.env.API_INTERNAL_URL;
  const originalPublicUrl = process.env.NEXT_PUBLIC_API_URL;

  beforeEach(() => {
    mockedFetch.mockReset();
    process.env.API_INTERNAL_URL = 'http://backend:8000/api/v1/';
    process.env.NEXT_PUBLIC_API_URL = 'http://public-backend.invalid/api/v1';
  });

  afterAll(() => {
    if (originalInternalUrl === undefined) delete process.env.API_INTERNAL_URL;
    else process.env.API_INTERNAL_URL = originalInternalUrl;
    if (originalPublicUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = originalPublicUrl;
  });

  it('forwards catalog pagination to the server-only backend URL', async () => {
    mockedFetch.mockResolvedValueOnce(upstreamResponse('{"items":[],"skip":24,"limit":24}'));

    const response = await getProducts(request('/api/products?skip=24&limit=24', 'GET'));

    expect(mockedFetch).toHaveBeenCalledWith(
      'http://backend:8000/api/v1/products?skip=24&limit=24',
      expect.objectContaining({ method: 'GET', cache: 'no-store' })
    );
    expect(String(mockedFetch.mock.calls[0][0])).not.toContain('public-backend.invalid');
    expect(response.status).toBe(200);
  });

  it('forwards product detail reads through the server-only backend URL', async () => {
    mockedFetch.mockResolvedValueOnce(upstreamResponse('{"id":"p1","name":"Product one"}'));

    const response = await getProduct(request('/api/products/p1', 'GET'), {
      params: { productId: 'p1' },
    });

    expect(mockedFetch).toHaveBeenCalledWith(
      'http://backend:8000/api/v1/products/p1',
      expect.objectContaining({ method: 'GET', cache: 'no-store' })
    );
    expect(response.status).toBe(200);
  });

  it('forwards the authenticated session cookie to cart and order reads and relays refreshed cookies', async () => {
    const headers = new Headers({ 'Content-Type': 'application/json' });
    headers.append('Set-Cookie', 'session_id=rotated; Path=/; HttpOnly; Secure; SameSite=Strict');
    mockedFetch
      .mockResolvedValueOnce(
        upstreamResponse('{"items":[],"subtotal":0,"currency":"INR"}', 200, headers)
      )
      .mockResolvedValueOnce(upstreamResponse('[]', 200, headers));

    const cart = await getCart(
      request('/api/cart', 'GET', undefined, { Cookie: 'session_id=active' })
    );
    await getOrders(request('/api/orders', 'GET', undefined, { Cookie: 'session_id=active' }));

    expect(forwardedHeaders(0).get('cookie')).toBe('session_id=active');
    expect(forwardedHeaders(1).get('cookie')).toBe('session_id=active');
    expect(cart.headers.get('set-cookie')).toContain('session_id=rotated');
    expect(mockedFetch.mock.calls[1][0]).toBe('http://backend:8000/api/v1/orders');
  });

  it.each([
    ['POST', addCartItem, '/api/cart/items', '/cart/items', '{"product_id":"p1","quantity":2}'],
    [
      'PUT',
      (req: Request) => setCartItemQuantity(req, { params: { productId: 'p1' } }),
      '/api/cart/items/p1',
      '/cart/items/p1',
      '{"quantity":3}',
    ],
    [
      'DELETE',
      (req: Request) => removeCartItem(req, { params: { productId: 'p1' } }),
      '/api/cart/items/p1',
      '/cart/items/p1',
      undefined,
    ],
  ])(
    'forwards cart %s cookie, CSRF token and request body where present',
    async (_method, handler, path, endpoint, body) => {
      mockedFetch.mockResolvedValueOnce(
        upstreamResponse('{"items":[],"subtotal":0,"currency":"INR"}')
      );
      const method = _method as string;
      const response = await handler(
        request(path as string, method, body as string | undefined, {
          ...(body ? { 'Content-Type': 'application/json' } : {}),
          Cookie: 'session_id=active',
          'X-CSRF-Token': 'csrf-token',
        })
      );

      expect(mockedFetch.mock.calls[0][0]).toBe(`http://backend:8000/api/v1${endpoint}`);
      expect(mockedFetch.mock.calls[0][1]).toEqual(expect.objectContaining({ method, body }));
      expect(forwardedHeaders().get('cookie')).toBe('session_id=active');
      expect(forwardedHeaders().get('x-csrf-token')).toBe('csrf-token');
      expect(response.status).toBe(200);
    }
  );

  it('forwards checkout cookie, CSRF, idempotency key and payload unchanged', async () => {
    mockedFetch.mockResolvedValueOnce(upstreamResponse('{"id":"o1"}', 201));
    const body = '{"items":[{"product_id":"p1","quantity":1}]}';

    const response = await checkout(
      request('/api/orders/checkout', 'POST', body, {
        'Content-Type': 'application/json',
        Cookie: 'session_id=active',
        'X-CSRF-Token': 'checkout-csrf',
        'Idempotency-Key': 'checkout-key-1',
      })
    );

    expect(mockedFetch.mock.calls[0][0]).toBe('http://backend:8000/api/v1/orders/checkout');
    expect(mockedFetch.mock.calls[0][1]).toEqual(expect.objectContaining({ method: 'POST', body }));
    expect(forwardedHeaders().get('cookie')).toBe('session_id=active');
    expect(forwardedHeaders().get('x-csrf-token')).toBe('checkout-csrf');
    expect(forwardedHeaders().get('idempotency-key')).toBe('checkout-key-1');
    expect(response.status).toBe(201);
  });

  it.each([401, 403, 404, 409, 422, 429, 500, 503])(
    'preserves safe upstream error status and body for %i',
    async (status) => {
      const body = JSON.stringify({
        detail: 'Safe upstream error',
        error_code: 'commerce_error',
        status_code: status,
      });
      mockedFetch.mockResolvedValueOnce(upstreamResponse(body, status));

      const response = await getCart(
        request('/api/cart', 'GET', undefined, { Cookie: 'session_id=active' })
      );

      expect(response.status).toBe(status);
      expect(await response.json()).toEqual(JSON.parse(body));
      expect(response.headers.get('cache-control')).toBe('no-store');
    }
  );

  it('returns a safe 503 without falling back to the public backend URL', async () => {
    delete process.env.API_INTERNAL_URL;

    const response = await getOrders(request('/api/orders', 'GET'));

    expect(mockedFetch).not.toHaveBeenCalled();
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({
      detail: 'Commerce service unavailable',
      error_code: 'commerce_service_unavailable',
      status_code: 503,
    });
  });
});
