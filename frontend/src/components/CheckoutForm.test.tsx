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
const deliveryAddress = {
  recipient_name: 'Portfolio Shopper',
  phone: '+91 98765 43210',
  address_line1: '12 Example Road',
  address_line2: null,
  city: 'Bengaluru',
  region: 'Karnataka',
  postal_code: '560001',
  country_code: 'IN' as const,
};

function fillDeliveryAddress() {
  for (const [label, value] of Object.entries({
    'Recipient name': deliveryAddress.recipient_name,
    Phone: deliveryAddress.phone,
    'Address line 1': deliveryAddress.address_line1,
    City: deliveryAddress.city,
    'State or region': deliveryAddress.region,
    'Postal code': deliveryAddress.postal_code,
  })) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
}
const placedOrder = {
  subtotal_cents: 2598,
  discount_total_cents: 0,
  promotion_snapshot: [],
  id: 'order-1',
  created_at: '2026-09-26T10:00:00Z',
  status: 'placed',
  total_cents: 2598,
  items: [
    {
      product_id: 'product-1',
      product_name: 'Canvas Weekender',
      product_sku: 'BAG-001',
      unit_price_cents: 1299,
      quantity: 2,
      line_total_cents: 2598,
    },
  ],
};

describe('CheckoutForm', () => {
  beforeEach(() => mockedCheckoutOrder.mockReset());

  it('submits only selected product ids and quantities, then reports success', async () => {
    mockedCheckoutOrder.mockResolvedValue(placedOrder);
    const onSuccess = jest.fn();
    render(<CheckoutForm items={[item]} onSuccess={onSuccess} />);

    fillDeliveryAddress();
    fireEvent.click(screen.getByRole('button', { name: /place demo order/i }));

    await waitFor(() => expect(mockedCheckoutOrder).toHaveBeenCalledTimes(1));
    expect(mockedCheckoutOrder.mock.calls[0][0]).toEqual([
      { product_id: 'product-1', quantity: 2 },
    ]);
    expect(mockedCheckoutOrder.mock.calls[0][1]).toEqual(expect.any(String));
    expect(mockedCheckoutOrder.mock.calls[0][3]).toEqual(deliveryAddress);
    expect(onSuccess).toHaveBeenCalledWith(placedOrder);
    expect(await screen.findByRole('status')).toHaveTextContent(/no payment is collected/i);
    expect(screen.getByRole('heading', { name: 'Order recorded' })).toBeInTheDocument();
    expect(screen.getByText(/SKU BAG-001/)).toBeInTheDocument();
    expect(screen.queryByText(/order-1/i)).not.toBeInTheDocument();
  });

  it('keeps checkout disabled when there are no selected items', () => {
    render(<CheckoutForm items={[]} />);
    expect(screen.getByRole('button', { name: /place demo order/i })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('no items');
  });

  it('forwards only the server-returned coupon code', async () => {
    mockedCheckoutOrder.mockResolvedValue(placedOrder);
    render(<CheckoutForm items={[item]} couponCode="SAVE10" />);

    fillDeliveryAddress();
    fireEvent.click(screen.getByRole('button', { name: /place demo order/i }));

    await waitFor(() => expect(mockedCheckoutOrder).toHaveBeenCalledTimes(1));
    expect(mockedCheckoutOrder.mock.calls[0][2]).toBe('SAVE10');
  });

  it('shows checkout failures and allows retrying', async () => {
    mockedCheckoutOrder.mockRejectedValueOnce(new Error('Insufficient stock'));
    render(<CheckoutForm items={[item]} />);

    fillDeliveryAddress();
    fireEvent.click(screen.getByRole('button', { name: /place demo order/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Insufficient stock');
    expect(screen.getByRole('button', { name: /place demo order/i })).toBeEnabled();
  });
});
