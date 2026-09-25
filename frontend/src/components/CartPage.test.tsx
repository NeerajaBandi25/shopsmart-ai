import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { CartPage } from './CartPage';

jest.mock('@/lib/cart-api', () => ({
  getCart: jest.fn(),
  removeCartItem: jest.fn(),
  setCartItemQuantity: jest.fn(),
}));

import { getCart, removeCartItem, setCartItemQuantity } from '@/lib/cart-api';

const emptyCart = { items: [], subtotal: 0, currency: 'USD' };
const filledCart = {
  items: [
    {
      product_id: 'lamp-1',
      name: 'Desk Lamp',
      sku: 'LAMP-1',
      unit_price: 1299,
      quantity: 1,
      line_total: 1299,
      stock_quantity: 8,
      max_purchase_quantity: 3,
    },
  ],
  subtotal: 1299,
  currency: 'USD',
};

describe('CartPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('shows loading and empty states', async () => {
    (getCart as jest.Mock).mockResolvedValue(emptyCart);
    render(<CartPage />);

    expect(screen.getByRole('status')).toHaveTextContent(/loading your cart/i);
    expect(await screen.findByText(/your cart is empty/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /browse products/i })).toHaveAttribute('href', '/');
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

  it('updates a quantity and displays the server total', async () => {
    (getCart as jest.Mock).mockResolvedValue(filledCart);
    (setCartItemQuantity as jest.Mock).mockResolvedValue({
      ...filledCart,
      items: [{ ...filledCart.items[0], quantity: 2, line_total: 2598 }],
      subtotal: 2598,
    });
    render(<CartPage />);

    const quantity = await screen.findByRole('spinbutton', { name: /quantity for desk lamp/i });
    fireEvent.change(quantity, { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: /update/i }));

    await waitFor(() => expect(setCartItemQuantity).toHaveBeenCalledWith('lamp-1', 2));
    expect(await screen.findAllByText('$25.98')).toHaveLength(2);
  });

  it('removes a cart item using the server response', async () => {
    (getCart as jest.Mock).mockResolvedValue(filledCart);
    (removeCartItem as jest.Mock).mockResolvedValue(emptyCart);
    render(<CartPage />);

    fireEvent.click(await screen.findByRole('button', { name: /remove/i }));

    await waitFor(() => expect(removeCartItem).toHaveBeenCalledWith('lamp-1'));
    expect(await screen.findByText(/your cart is empty/i)).toBeInTheDocument();
  });
});
