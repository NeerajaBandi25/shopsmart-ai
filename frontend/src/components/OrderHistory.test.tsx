import { render, screen } from '@testing-library/react';
import { OrderHistory } from '@/components/OrderHistory';
import { getOrders } from '@/lib/order-api';

jest.mock('@/lib/order-api', () => ({ getOrders: jest.fn() }));

const mockedGetOrders = jest.mocked(getOrders);

describe('OrderHistory', () => {
  beforeEach(() => mockedGetOrders.mockReset());

  it('renders persisted order and immutable line snapshots', async () => {
    mockedGetOrders.mockResolvedValue([
      {
        id: 'order-42',
        created_at: '2026-09-26T10:00:00Z',
        status: 'placed',
        subtotal_cents: 2598,
        discount_total_cents: 0,
        total_cents: 2598,
        promotion_snapshot: [],
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
      },
    ]);

    render(<OrderHistory />);

    expect(await screen.findByRole('heading', { name: /^Order from/ })).toBeInTheDocument();
    expect(screen.queryByText(/order-42/i)).not.toBeInTheDocument();
    expect(screen.getByText('Canvas Weekender')).toBeInTheDocument();
    expect(screen.getByText('2 × ₹12.99')).toBeInTheDocument();
    expect(screen.getAllByText('₹25.98')).toHaveLength(3);
  });

  it('shows empty and error states', async () => {
    mockedGetOrders.mockResolvedValueOnce([]).mockRejectedValueOnce(new Error('Try later'));
    const { rerender } = render(<OrderHistory />);
    expect(await screen.findByText('No orders yet.')).toBeInTheDocument();
    rerender(<OrderHistory key="retry" />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Try later');
  });
});
