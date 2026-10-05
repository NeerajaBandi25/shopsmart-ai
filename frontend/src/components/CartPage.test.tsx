import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { CartPage } from './CartPage';
import { useCommerceStore } from '@/lib/commerce-store';

jest.mock('@/lib/cart-api', () => ({
  applyCartCoupon: jest.fn(),
  getCart: jest.fn(),
  removeCartCoupon: jest.fn(),
  removeCartItem: jest.fn(),
  setCartItemQuantity: jest.fn(),
}));

import {
  applyCartCoupon,
  getCart,
  removeCartCoupon,
  removeCartItem,
  setCartItemQuantity,
} from '@/lib/cart-api';

const quoteFields = {
  coupon_code: null,
  coupon_evaluation: null,
  applied_promotions: [],
  discount_total_cents: 0,
  total_cents: 0,
};
const emptyCart = { ...quoteFields, items: [], subtotal: 0, currency: 'INR' };
const filledCart = {
  ...quoteFields,
  items: [
    {
      product_id: 'lamp-1',
      name: 'Desk Lamp',
      sku: 'LAMP-1',
      image_url: '/images/products/portfolio/cart-lamp.png',
      image_alt: 'Desk lamp illustration',
      unit_price: 1299,
      quantity: 1,
      line_total: 1299,
      stock_quantity: 8,
      max_purchase_quantity: 3,
    },
  ],
  subtotal: 1299,
  currency: 'INR',
  total_cents: 1299,
};

describe('CartPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useCommerceStore.getState().clearPrivateCommerce();
  });

  it('shows loading and empty states', async () => {
    (getCart as jest.Mock).mockResolvedValue(emptyCart);
    render(<CartPage />);

    expect(screen.getByRole('status')).toHaveTextContent(/loading your cart/i);
    expect(await screen.findByText(/your cart is empty/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /browse products/i })).toHaveAttribute('href', '/');
    expect(useCommerceStore.getState().cartItemCount).toBe(0);
  });

  it('shows a load error and allows retry', async () => {
    (getCart as jest.Mock)
      .mockRejectedValueOnce(new Error('Sign in required.'))
      .mockResolvedValueOnce(emptyCart);
    render(<CartPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Sign in required.');
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(await screen.findByText(/your cart is empty/i)).toBeInTheDocument();
    expect(getCart).toHaveBeenCalledTimes(2);
  });

  it('shows the server quote guidance and integer stock-limited quantity control', async () => {
    (getCart as jest.Mock).mockResolvedValue(filledCart);
    render(<CartPage />);

    const quantity = await screen.findByRole('spinbutton', { name: /quantity for desk lamp/i });
    expect(quantity).toHaveAttribute('step', '1');
    expect(quantity).toHaveAttribute('max', '3');
    expect(screen.getByRole('img', { name: 'Desk lamp illustration' })).toBeInTheDocument();
    expect(
      screen.getByText(/prices and promotions are calculated by shopsmart/i)
    ).toBeInTheDocument();
  });

  it('updates a quantity and displays the server total', async () => {
    (getCart as jest.Mock).mockResolvedValue(filledCart);
    (setCartItemQuantity as jest.Mock).mockResolvedValue({
      ...filledCart,
      items: [{ ...filledCart.items[0], quantity: 2, line_total: 2598 }],
      subtotal: 2598,
      total_cents: 2598,
    });
    render(<CartPage />);

    const quantity = await screen.findByRole('spinbutton', { name: /quantity for desk lamp/i });
    fireEvent.change(quantity, { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: /update/i }));

    await waitFor(() => expect(setCartItemQuantity).toHaveBeenCalledWith('lamp-1', 2));
    expect(await screen.findAllByText('₹25.98')).toHaveLength(3);
    expect(useCommerceStore.getState().cartItemCount).toBe(2);
  });

  it('removes a cart item using the server response', async () => {
    (getCart as jest.Mock).mockResolvedValue(filledCart);
    (removeCartItem as jest.Mock).mockResolvedValue(emptyCart);
    render(<CartPage />);

    fireEvent.click(await screen.findByRole('button', { name: /remove/i }));

    await waitFor(() => expect(removeCartItem).toHaveBeenCalledWith('lamp-1'));
    expect(await screen.findByText(/your cart is empty/i)).toBeInTheDocument();
    expect(useCommerceStore.getState().cartItemCount).toBe(0);
  });

  it('does not change the shared count when a quantity update fails', async () => {
    (getCart as jest.Mock).mockResolvedValue(filledCart);
    (setCartItemQuantity as jest.Mock).mockRejectedValue(new Error('Update failed.'));
    render(<CartPage />);

    fireEvent.change(await screen.findByRole('spinbutton', { name: /quantity for desk lamp/i }), {
      target: { value: '2' },
    });
    fireEvent.click(screen.getByRole('button', { name: /update/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Update failed.');
    expect(useCommerceStore.getState().cartItemCount).toBe(1);
  });

  it('applies and removes a coupon using the server quote', async () => {
    const discountedCart = {
      ...filledCart,
      coupon_code: 'SAVE10',
      coupon_evaluation: {
        promotion_id: 'promo-1',
        code: 'SAVE10',
        name: 'Ten percent',
        eligible: true,
        reason_code: 'eligible',
        discount_cents: 130,
        applied_scope: { type: 'all' },
      },
      applied_promotions: [
        {
          promotion_id: 'promo-1',
          code: 'SAVE10',
          name: 'Ten percent',
          promotion_type: 'percentage',
          value: 10,
          discount_cents: 130,
          applied_scope: { type: 'all' },
        },
      ],
      discount_total_cents: 130,
      total_cents: 1169,
    };
    (getCart as jest.Mock).mockResolvedValue(filledCart);
    (applyCartCoupon as jest.Mock).mockResolvedValue(discountedCart);
    (removeCartCoupon as jest.Mock).mockResolvedValue(filledCart);
    render(<CartPage />);

    fireEvent.change(await screen.findByLabelText(/coupon code/i), {
      target: { value: 'save10' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(await screen.findByText('Ten percent')).toBeInTheDocument();
    expect(screen.getByText('₹11.69')).toBeInTheDocument();
    expect(applyCartCoupon).toHaveBeenCalledWith('save10');
    fireEvent.click(screen.getByRole('button', { name: 'Remove coupon' }));
    await waitFor(() => expect(removeCartCoupon).toHaveBeenCalledTimes(1));
    expect(await screen.findAllByText('₹12.99')).toHaveLength(3);
  });
});
