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
const quoteFields = {
  coupon_code: null,
  coupon_evaluation: null,
  applied_promotions: [],
  discount_total_cents: 0,
  total_cents: 0,
};
const orderPricing = { subtotal_cents: 2598, discount_total_cents: 0, promotion_snapshot: [] };

function fillDeliveryAddress() {
  for (const [label, value] of Object.entries({
    'Recipient name': 'Portfolio Shopper',
    Phone: '+91 98765 43210',
    'Address line 1': '12 Example Road',
    City: 'Bengaluru',
    'State or region': 'Karnataka',
    'Postal code': '560001',
  })) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
}

describe('CheckoutFlow', () => {
  beforeEach(() => {
    mockedGetCart.mockReset();
    mockedRemoveCartItem.mockReset();
    mockedCheckoutOrder.mockReset();
    useCommerceStore.getState().clearPrivateCommerce();
  });

  it('checks out current cart lines and clears them only after the order succeeds', async () => {
    mockedGetCart.mockResolvedValue({
      ...quoteFields,
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
      currency: 'INR',
      coupon_code: 'SAVE10',
      discount_total_cents: 200,
      total_cents: 2398,
    });
    mockedCheckoutOrder.mockResolvedValue({
      ...orderPricing,
      id: 'order-1',
      created_at: '2026-09-26T10:00:00Z',
      status: 'placed',
      total_cents: 2398,
      items: [],
    });
    mockedRemoveCartItem.mockResolvedValue({
      ...quoteFields,
      items: [],
      subtotal: 0,
      currency: 'INR',
    });

    render(<CheckoutFlow />);
    const placeOrder = await screen.findByRole('button', { name: /place demo order/i });
    expect(useCommerceStore.getState().cartItemCount).toBe(2);
    fillDeliveryAddress();
    fireEvent.click(placeOrder);

    await screen.findByRole('heading', { name: 'Order recorded' });
    expect(screen.getByRole('status')).toHaveTextContent(/no payment is collected/i);
    expect(screen.queryByText(/order-1/i)).not.toBeInTheDocument();
    await waitFor(() => expect(mockedRemoveCartItem).toHaveBeenCalledWith('product-1'));
    expect(useCommerceStore.getState().cartItemCount).toBe(0);
    expect(mockedCheckoutOrder.mock.calls[0][0]).toEqual([
      { product_id: 'product-1', quantity: 2 },
    ]);
    expect(mockedCheckoutOrder.mock.calls[0][2]).toBe('SAVE10');
    expect(mockedCheckoutOrder.mock.calls[0][3]).toEqual(
      expect.objectContaining({ city: 'Bengaluru', country_code: 'IN' })
    );
  });

  it('keeps the count and reports a warning when all cart removals fail', async () => {
    mockedGetCart.mockResolvedValue({
      ...quoteFields,
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
      currency: 'INR',
      total_cents: 2598,
    });
    mockedCheckoutOrder.mockResolvedValue({
      ...orderPricing,
      id: 'order-1',
      created_at: '2026-09-26T10:00:00Z',
      status: 'placed',
      total_cents: 2598,
      items: [],
    });
    mockedRemoveCartItem.mockRejectedValue(new Error('Cleanup failed'));
    mockedGetCart.mockResolvedValueOnce({
      ...quoteFields,
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
      currency: 'INR',
    });

    render(<CheckoutFlow />);
    const placeOrder = await screen.findByRole('button', { name: /place demo order/i });
    fillDeliveryAddress();
    fireEvent.click(placeOrder);

    await screen.findByRole('heading', { name: 'Order recorded' });
    expect(await screen.findByRole('alert')).toHaveTextContent('cart could not be fully cleared');
    await waitFor(() => expect(mockedGetCart).toHaveBeenCalledTimes(2));
    expect(useCommerceStore.getState().cartItemCount).toBe(2);
  });

  it('uses an authoritative cart refresh after mixed removals resolve out of order', async () => {
    const initialCart = {
      ...quoteFields,
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
      currency: 'INR',
      total_cents: 3398,
    };
    const staleSnapshot = {
      ...quoteFields,
      items: [{ ...initialCart.items[1], quantity: 2 }, initialCart.items[2]],
      subtotal: 1300,
      currency: 'INR',
      total_cents: 1300,
    };
    const newerSnapshot = {
      ...quoteFields,
      items: [initialCart.items[2]],
      subtotal: 300,
      currency: 'INR',
      total_cents: 300,
    };
    const authoritativeCart = {
      ...quoteFields,
      items: [{ ...initialCart.items[1], quantity: 1 }],
      subtotal: 500,
      currency: 'INR',
      total_cents: 500,
    };
    let resolveFirst!: (cart: typeof staleSnapshot) => void;
    let resolveSecond!: (cart: typeof newerSnapshot) => void;
    let rejectThird!: (reason: Error) => void;
    mockedGetCart.mockResolvedValueOnce(initialCart).mockResolvedValueOnce(authoritativeCart);
    mockedCheckoutOrder.mockResolvedValue({
      ...orderPricing,
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
    const placeOrder = await screen.findByRole('button', { name: /place demo order/i });
    fillDeliveryAddress();
    fireEvent.click(placeOrder);
    await screen.findByRole('heading', { name: 'Order recorded' });
    await waitFor(() => expect(mockedRemoveCartItem).toHaveBeenCalledTimes(3));

    resolveSecond(newerSnapshot);
    resolveFirst(staleSnapshot);
    rejectThird(new Error('Cleanup failed'));

    expect(await screen.findByRole('alert')).toHaveTextContent('cart could not be fully cleared');
    await waitFor(() => expect(mockedGetCart).toHaveBeenCalledTimes(2));
    expect(useCommerceStore.getState().cartItemCount).toBe(1);
  });
});
