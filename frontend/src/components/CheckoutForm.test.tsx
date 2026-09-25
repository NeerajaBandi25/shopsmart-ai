import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CheckoutForm } from '@/components/CheckoutForm';
import { checkoutOrder } from '@/lib/order-api';

jest.mock('@/lib/order-api', () => ({ checkoutOrder: jest.fn() }));
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const mockedCheckoutOrder = jest.mocked(checkoutOrder);
const item = { product_id: 'product-1', quantity: 2, product_name: 'Canvas Weekender' };
const placedOrder = {
  id: 'order-1',
  created_at: '2026-09-26T10:00:00Z',
  status: 'placed',
  total_cents: 2598,
  items: [],
};

describe('CheckoutForm', () => {
  beforeEach(() => mockedCheckoutOrder.mockReset());

  it('submits only selected product ids and quantities, then reports success', async () => {
    mockedCheckoutOrder.mockResolvedValue(placedOrder);
    const onSuccess = jest.fn();
    render(<CheckoutForm items={[item]} onSuccess={onSuccess} />);

    fireEvent.click(screen.getByRole('button', { name: 'Place order' }));

    await waitFor(() => expect(mockedCheckoutOrder).toHaveBeenCalledTimes(1));
    expect(mockedCheckoutOrder.mock.calls[0][0]).toEqual([
      { product_id: 'product-1', quantity: 2 },
    ]);
    expect(mockedCheckoutOrder.mock.calls[0][1]).toEqual(expect.any(String));
    expect(onSuccess).toHaveBeenCalledWith(placedOrder);
    expect(await screen.findByRole('status')).toHaveTextContent('Order placed successfully.');
  });

  it('keeps checkout disabled when there are no selected items', () => {
    render(<CheckoutForm items={[]} />);
    expect(screen.getByRole('button', { name: 'Place order' })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('no items');
  });

  it('shows checkout failures and allows retrying', async () => {
    mockedCheckoutOrder.mockRejectedValueOnce(new Error('Insufficient stock'));
    render(<CheckoutForm items={[item]} />);

    fireEvent.click(screen.getByRole('button', { name: 'Place order' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Insufficient stock');
    expect(screen.getByRole('button', { name: 'Place order' })).toBeEnabled();
  });
});
