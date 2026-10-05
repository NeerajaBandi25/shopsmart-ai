import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import CheckoutCompletePage from './page';
import { getCart } from '@/lib/cart-api';
import { getOrder, retryPayment } from '@/lib/order-api';

jest.mock('@/lib/cart-api', () => ({ getCart: jest.fn() }));
jest.mock('@/lib/order-api', () => ({ getOrder: jest.fn(), retryPayment: jest.fn() }));
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const orderId = '00000000-0000-4000-8000-000000000001';
const order = {
  id: orderId,
  created_at: '2026-10-04T10:00:00Z',
  status: 'paid',
  payment_status: 'succeeded' as const,
  payment_method_label: null,
  subtotal_cents: 1000,
  discount_total_cents: 0,
  total_cents: 1000,
  promotion_snapshot: [],
  items: [],
};

describe('CheckoutCompletePage', () => {
  beforeEach(() => {
    jest.mocked(getOrder).mockReset();
    jest.mocked(retryPayment).mockReset();
    jest.mocked(getCart).mockReset();
    window.history.replaceState({}, '', `/checkout/complete?payment=success&order_id=${orderId}`);
  });

  it('shows payment success only after the owner-scoped API reports succeeded', async () => {
    jest.mocked(getOrder).mockResolvedValue(order);
    jest.mocked(getCart).mockResolvedValue({ items: [] } as never);

    render(<CheckoutCompletePage />);

    expect(await screen.findByRole('heading', { name: 'Payment confirmed' })).toBeInTheDocument();
    expect(getOrder).toHaveBeenCalledWith(orderId);
    await waitFor(() => expect(getCart).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('link', { name: /view order history/i })).toHaveAttribute(
      'href',
      '/orders'
    );
  });

  it('does not treat a success query parameter as payment proof', async () => {
    jest.mocked(getOrder).mockResolvedValue({ ...order, payment_status: 'pending' });
    jest.useFakeTimers();

    render(<CheckoutCompletePage />);
    await act(async () => {
      await jest.advanceTimersByTimeAsync(10_500);
    });

    expect(screen.getByText(/payment confirmation is still processing/i)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Payment confirmed' })).not.toBeInTheDocument();
    expect(getCart).not.toHaveBeenCalled();
    jest.useRealTimers();
  });

  it('retries payment against the same order and validates the hosted destination', async () => {
    jest
      .mocked(getOrder)
      .mockResolvedValue({ ...order, status: 'pending_payment', payment_status: 'failed' });
    jest.mocked(retryPayment).mockResolvedValue({
      ...order,
      status: 'pending_payment',
      payment_status: 'requires_action',
      checkout_url: 'https://checkout.stripe.com/c/pay/cs_test_retry',
    });
    const onRedirect = jest.fn();
    render(<CheckoutCompletePage onRedirect={onRedirect} />);

    fireEvent.click(await screen.findByRole('button', { name: /retry payment for this order/i }));

    await waitFor(() => expect(retryPayment).toHaveBeenCalledWith(orderId));
    expect(onRedirect).toHaveBeenCalledWith('https://checkout.stripe.com/c/pay/cs_test_retry');
  });

  it('clears the saved checkout key after the API confirms terminal cancellation', async () => {
    window.sessionStorage.setItem(
      'shopsmart.checkout.idempotency.v1',
      JSON.stringify({ fingerprint: 'old-cart', key: 'old-order-key' })
    );
    jest.mocked(getOrder).mockResolvedValue({
      ...order,
      status: 'cancelled',
      payment_status: 'cancelled',
    });
    render(<CheckoutCompletePage />);

    expect(await screen.findByText(/checkout was cancelled/i)).toBeInTheDocument();
    await waitFor(() =>
      expect(window.sessionStorage.getItem('shopsmart.checkout.idempotency.v1')).toBeNull()
    );
  });
});
