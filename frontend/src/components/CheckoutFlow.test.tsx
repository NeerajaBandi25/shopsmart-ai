import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CheckoutFlow } from '@/components/CheckoutFlow';
import { getCart, removeCartItem } from '@/lib/cart-api';
import { checkoutOrder } from '@/lib/order-api';
import { useCommerceStore } from '@/lib/commerce-store';

jest.mock('@/lib/cart-api', () => ({
  getCart: jest.fn(),
  removeCartItem: jest.fn(),
}));
jest.mock('@/lib/order-api', () => ({ checkoutOrder: jest.fn() }));
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const mockedGetCart = jest.mocked(getCart);
const mockedRemoveCartItem = jest.mocked(removeCartItem);
const mockedCheckoutOrder = jest.mocked(checkoutOrder);

describe('CheckoutFlow', () => {
  beforeEach(() => {
    mockedGetCart.mockReset();
    mockedRemoveCartItem.mockReset();
    mockedCheckoutOrder.mockReset();
    useCommerceStore.getState().clearPrivateCommerce();
  });

  it('checks out current cart lines and clears them only after the order succeeds', async () => {
    mockedGetCart.mockResolvedValue({
      items: [
        {
          product_id: 'product-1',
          name: 'Canvas Weekender',
          sku: 'BAG-001',
          unit_price: 1299,
          quantity: 2,
          line_total: 2598,
          stock_quantity: 8,
          max_purchase_quantity: 3,
        },
      ],
      subtotal: 2598,
      currency: 'USD',
    });
    mockedCheckoutOrder.mockResolvedValue({
      id: 'order-1',
      created_at: '2026-09-26T10:00:00Z',
      status: 'placed',
      total_cents: 2598,
      items: [],
    });
    mockedRemoveCartItem.mockResolvedValue({ items: [], subtotal: 0, currency: 'USD' });

    render(<CheckoutFlow />);
    const placeOrder = await screen.findByRole('button', { name: 'Place order' });
    expect(useCommerceStore.getState().cartItemCount).toBe(2);
    fireEvent.click(placeOrder);

    await screen.findByText('Order #order-1');
    await waitFor(() => expect(mockedRemoveCartItem).toHaveBeenCalledWith('product-1'));
    expect(useCommerceStore.getState().cartItemCount).toBe(0);
    expect(mockedCheckoutOrder.mock.calls[0][0]).toEqual([
      { product_id: 'product-1', quantity: 2 },
    ]);
  });

  it('keeps the count and reports a warning when all cart removals fail', async () => {
    mockedGetCart.mockResolvedValue({
      items: [
        {
          product_id: 'product-1',
          name: 'Canvas Weekender',
          sku: 'BAG-001',
          unit_price: 1299,
          quantity: 2,
          line_total: 2598,
          stock_quantity: 8,
          max_purchase_quantity: 3,
        },
      ],
      subtotal: 2598,
      currency: 'USD',
    });
    mockedCheckoutOrder.mockResolvedValue({
      id: 'order-1',
      created_at: '2026-09-26T10:00:00Z',
      status: 'placed',
      total_cents: 2598,
      items: [],
    });
    mockedRemoveCartItem.mockRejectedValue(new Error('Cleanup failed'));
    mockedGetCart.mockResolvedValueOnce({
      items: [
        {
          product_id: 'product-1',
          name: 'Canvas Weekender',
          sku: 'BAG-001',
          unit_price: 1299,
          quantity: 2,
          line_total: 2598,
          stock_quantity: 8,
          max_purchase_quantity: 3,
        },
      ],
      subtotal: 2598,
      currency: 'USD',
    });

    render(<CheckoutFlow />);
    fireEvent.click(await screen.findByRole('button', { name: 'Place order' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('cart could not be fully cleared');
    await waitFor(() => expect(mockedGetCart).toHaveBeenCalledTimes(2));
    expect(useCommerceStore.getState().cartItemCount).toBe(2);
  });

  it('uses an authoritative cart refresh after mixed removals resolve out of order', async () => {
    const initialCart = {
      items: [
        {
          product_id: 'product-1',
          name: 'Canvas Weekender',
          sku: 'BAG-001',
          unit_price: 1299,
          quantity: 2,
          line_total: 2598,
          stock_quantity: 8,
          max_purchase_quantity: 3,
        },
        {
          product_id: 'product-2',
          name: 'Desk Lamp',
          sku: 'LAMP-001',
          unit_price: 500,
          quantity: 1,
          line_total: 500,
          stock_quantity: 8,
          max_purchase_quantity: 3,
        },
        {
          product_id: 'product-3',
          name: 'Notebook',
          sku: 'NOTE-001',
          unit_price: 300,
          quantity: 1,
          line_total: 300,
          stock_quantity: 8,
          max_purchase_quantity: 3,
        },
      ],
      subtotal: 3398,
      currency: 'USD',
    };
    const staleSnapshot = {
      items: [{ ...initialCart.items[1], quantity: 2 }, initialCart.items[2]],
      subtotal: 1300,
      currency: 'USD',
    };
    const newerSnapshot = {
      items: [initialCart.items[2]],
      subtotal: 300,
      currency: 'USD',
    };
    const authoritativeCart = {
      items: [{ ...initialCart.items[1], quantity: 1 }],
      subtotal: 500,
      currency: 'USD',
    };
    let resolveFirst!: (cart: typeof staleSnapshot) => void;
    let resolveSecond!: (cart: typeof newerSnapshot) => void;
    let rejectThird!: (reason: Error) => void;
    mockedGetCart.mockResolvedValueOnce(initialCart).mockResolvedValueOnce(authoritativeCart);
    mockedCheckoutOrder.mockResolvedValue({
      id: 'order-1',
      created_at: '2026-09-26T10:00:00Z',
      status: 'placed',
      total_cents: 3398,
      items: [],
    });
    mockedRemoveCartItem
      .mockReturnValueOnce(new Promise((resolve) => (resolveFirst = resolve)))
      .mockReturnValueOnce(new Promise((resolve) => (resolveSecond = resolve)))
      .mockReturnValueOnce(new Promise((_, reject) => (rejectThird = reject)));

    render(<CheckoutFlow />);
    fireEvent.click(await screen.findByRole('button', { name: 'Place order' }));
    await screen.findByText('Order #order-1');
    await waitFor(() => expect(mockedRemoveCartItem).toHaveBeenCalledTimes(3));

    resolveSecond(newerSnapshot);
    resolveFirst(staleSnapshot);
    rejectThird(new Error('Cleanup failed'));

    expect(await screen.findByRole('alert')).toHaveTextContent('cart could not be fully cleared');
    await waitFor(() => expect(mockedGetCart).toHaveBeenCalledTimes(2));
    expect(useCommerceStore.getState().cartItemCount).toBe(1);
  });
});
