import { addCartItem, getCart, removeCartItem, setCartItemQuantity } from './cart-api';

const mockedFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockedFetch;

const cart = { items: [], subtotal: 0, currency: 'USD' };
const jsonResponse = (body: unknown, status = 200): Response =>
  ({ ok: status >= 200 && status < 300, status, json: async () => body }) as Response;

describe('same-origin cart API routes', () => {
  const originalPublicUrl = process.env.NEXT_PUBLIC_API_URL;

  beforeEach(() => {
    mockedFetch.mockReset();
    process.env.NEXT_PUBLIC_API_URL = 'https://backend.invalid/api/v1';
  });

  afterAll(() => {
    if (originalPublicUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = originalPublicUrl;
  });

  it('retrieves the cart through the same-origin route with credentials', async () => {
    mockedFetch.mockResolvedValueOnce(jsonResponse(cart));

    await expect(getCart()).resolves.toEqual(cart);

    expect(mockedFetch).toHaveBeenCalledWith(
      '/api/cart',
      expect.objectContaining({ method: 'GET', credentials: 'include' })
    );
  });

  it('adds, updates, and removes items through same-origin routes with session and CSRF credentials', async () => {
    mockedFetch
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'csrf-1' }))
      .mockResolvedValueOnce(jsonResponse(cart))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'csrf-2' }))
      .mockResolvedValueOnce(jsonResponse(cart))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: 'csrf-3' }))
      .mockResolvedValueOnce(jsonResponse(cart));

    await addCartItem('product-1', 2);
    await setCartItemQuantity('product-1', 3);
    await removeCartItem('product-1');

    expect(mockedFetch.mock.calls.map(([url]) => url)).toEqual([
      '/api/auth/csrf',
      '/api/cart/items',
      '/api/auth/csrf',
      '/api/cart/items/product-1',
      '/api/auth/csrf',
      '/api/cart/items/product-1',
    ]);
    expect(mockedFetch.mock.calls[1][1]).toEqual(
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ product_id: 'product-1', quantity: 2 }),
        headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-1' }),
      })
    );
    expect(mockedFetch.mock.calls[3][1]).toEqual(
      expect.objectContaining({
        method: 'PUT',
        credentials: 'include',
        body: JSON.stringify({ quantity: 3 }),
        headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-2' }),
      })
    );
    expect(mockedFetch.mock.calls[5][1]).toEqual(
      expect.objectContaining({
        method: 'DELETE',
        credentials: 'include',
        headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-3' }),
      })
    );
    expect(mockedFetch.mock.calls.every(([url]) => !String(url).includes('backend.invalid'))).toBe(
      true
    );
  });
});
