import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { AddToCartButton } from './AddToCartButton';

jest.mock('@/lib/cart-api', () => ({
  addCartItem: jest.fn(),
}));

import { addCartItem } from '@/lib/cart-api';

describe('AddToCartButton', () => {
  beforeEach(() => jest.clearAllMocks());

  it('adds the selected quantity and reports success', async () => {
    (addCartItem as jest.Mock).mockResolvedValue({});
    render(<AddToCartButton productId="lamp-1" stockQuantity={8} maxPurchaseQuantity={3} />);

    fireEvent.change(screen.getByRole('spinbutton', { name: /quantity/i }), {
      target: { value: '2' },
    });
    fireEvent.click(screen.getByRole('button', { name: /add to cart/i }));

    await waitFor(() => expect(addCartItem).toHaveBeenCalledWith('lamp-1', 2));
    expect(await screen.findByRole('status')).toHaveTextContent(/added to cart/i);
  });

  it('prevents quantities above available limits', () => {
    render(<AddToCartButton productId="lamp-1" stockQuantity={2} maxPurchaseQuantity={5} />);

    fireEvent.change(screen.getByRole('spinbutton', { name: /quantity/i }), {
      target: { value: '3' },
    });

    expect(screen.getByRole('button', { name: /add to cart/i })).toBeDisabled();
  });

  it('shows an API error', async () => {
    (addCartItem as jest.Mock).mockRejectedValue(new Error('Sign in first.'));
    render(<AddToCartButton productId="lamp-1" stockQuantity={8} maxPurchaseQuantity={3} />);

    fireEvent.click(screen.getByRole('button', { name: /add to cart/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Sign in first.');
  });
});
