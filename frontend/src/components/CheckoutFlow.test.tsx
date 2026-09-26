import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CheckoutFlow } from '@/components/CheckoutFlow';
import { getCart, removeCartItem } from '@/lib/cart-api';
import { checkoutOrder } from '@/lib/order-api';

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
    fireEvent.click(await screen.findByRole('button', { name: 'Place order' }));

    await screen.findByText('Order #order-1');
    await waitFor(() => expect(mockedRemoveCartItem).toHaveBeenCalledWith('product-1'));
    expect(mockedCheckoutOrder.mock.calls[0][0]).toEqual([
      { product_id: 'product-1', quantity: 2 },
    ]);
  });
});
