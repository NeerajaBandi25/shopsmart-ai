import { fireEvent, render, screen } from '@testing-library/react';
import { CheckoutFlow } from '@/components/CheckoutFlow';
import { getCart } from '@/lib/cart-api';
import { checkoutOrder } from '@/lib/order-api';
import { useCommerceStore } from '@/lib/commerce-store';

jest.mock('@/lib/cart-api', () => ({ getCart: jest.fn() }));
jest.mock('@/lib/order-api', () => ({ checkoutOrder: jest.fn() }));
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const mockedGetCart = jest.mocked(getCart);
const mockedCheckoutOrder = jest.mocked(checkoutOrder);
const cart = {
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
  coupon_evaluation: null,
  applied_promotions: [],
  discount_total_cents: 200,
  total_cents: 2398,
};
const paymentSession = {
  id: '00000000-0000-4000-8000-000000000001',
  created_at: '2026-10-04T10:00:00Z',
  status: 'pending_payment',
  payment_status: 'requires_action' as const,
  checkout_url: 'https://checkout.stripe.com/c/pay/cs_test_example',
  subtotal_cents: 2598,
  discount_total_cents: 200,
  total_cents: 2398,
  promotion_snapshot: [],
  items: [],
};

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
    mockedGetCart.mockReset().mockResolvedValue(cart);
    mockedCheckoutOrder.mockReset().mockResolvedValue(paymentSession);
    useCommerceStore.getState().clearPrivateCommerce();
    window.history.replaceState({}, '', '/checkout');
  });

  it('redirects to hosted test checkout and leaves cart state until payment is verified', async () => {
    const onRedirect = jest.fn();
    render(<CheckoutFlow onRedirect={onRedirect} />);
    const continueButton = await screen.findByRole('button', {
      name: /continue to secure checkout/i,
    });
    expect(useCommerceStore.getState().cartItemCount).toBe(2);
    fillDeliveryAddress();
    fireEvent.click(continueButton);

    expect(await screen.findByText(/no live payment is processed/i)).toBeInTheDocument();
    expect(onRedirect).toHaveBeenCalledWith(paymentSession.checkout_url);
    expect(mockedCheckoutOrder.mock.calls[0][0]).toEqual([
      { product_id: 'product-1', quantity: 2 },
    ]);
    expect(mockedCheckoutOrder.mock.calls[0][2]).toBe('SAVE10');
    expect(useCommerceStore.getState().cartItemCount).toBe(2);
  });

  it('keeps the cart on a cancelled-provider return', async () => {
    window.history.replaceState({}, '', '/checkout?payment=cancelled');
    render(<CheckoutFlow />);

    expect(await screen.findByText(/checkout was cancelled/i)).toBeInTheDocument();
    expect(
      await screen.findByRole('button', { name: /continue to secure checkout/i })
    ).toBeEnabled();
    expect(mockedGetCart).toHaveBeenCalledTimes(1);
    expect(useCommerceStore.getState().cartItemCount).toBe(2);
  });

  it('shows a safe configuration error without losing the cart', async () => {
    mockedCheckoutOrder.mockRejectedValue(new Error('Sandbox payments are not configured'));
    render(<CheckoutFlow />);
    await screen.findByRole('button', { name: /continue to secure checkout/i });
    fillDeliveryAddress();
    fireEvent.click(await screen.findByRole('button', { name: /continue to secure checkout/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /sandbox payments are not configured/i
    );
    expect(useCommerceStore.getState().cartItemCount).toBe(2);
  });
});
