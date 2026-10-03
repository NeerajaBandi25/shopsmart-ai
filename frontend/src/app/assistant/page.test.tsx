import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import AssistantPage from './page';

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: mockPush }) }));

jest.mock('@/app/authenticated-layout', () => {
  function MockAuthenticatedLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>;
  }

  return { __esModule: true, default: MockAuthenticatedLayout };
});

describe('shopping assistant page', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
    mockPush.mockClear();
  });

  it('navigates only an authoritative checkout response with a populated cart', async () => {
    const fetchMock = global.fetch as jest.Mock;
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'csrf' }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          conversation_id: 'c-1',
          message_id: 'm-1',
          answer: 'Ready for checkout.',
          answerable: true,
          citations: [],
          intent: 'CHECKOUT',
          result_data: {
            navigation: '/checkout',
            cart: { items: [{ name: 'Laptop', quantity: 1, line_total: 100 }], subtotal: 100 },
          },
        }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => [] });
    render(<AssistantPage />);
    fireEvent.change(screen.getByLabelText('Message the shopping assistant'), {
      target: { value: 'Take me to checkout' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/checkout'));
  });

  it('shows commerce prompts without a customer document upload workflow', async () => {
    const fetchMock = global.fetch as jest.Mock;
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'csrf' }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          conversation_id: 'conversation-1',
          message_id: 'message-1',
          answer: 'I found 1 product matching your request.',
          answerable: true,
          reason: null,
          intent: 'PRODUCT_SEARCH',
          citations: [],
          result_data: {
            products: [
              {
                id: 'product-1',
                name: 'Wireless headphones',
                description: 'Over-ear',
                sku: 'HP-1',
                price_cents: 4999,
                stock_quantity: 3,
              },
            ],
          },
        }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => [] });

    render(<AssistantPage />);

    expect(screen.getByRole('heading', { name: 'Shopping assistant' })).toBeInTheDocument();
    expect(screen.queryByText(/add a text document/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Find in-stock products under ₹5,000' }));

    expect(await screen.findByText('Wireless headphones')).toBeInTheDocument();
    expect(screen.getByText('₹49.99')).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
  });

  it('compares returned catalog fields and adds a selected product through the cart API', async () => {
    const fetchMock = global.fetch as jest.Mock;
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'csrf-token' }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          conversation_id: 'conversation-1',
          message_id: 'message-1',
          answer: 'Here are two catalog products.',
          answerable: true,
          reason: null,
          intent: 'PRODUCT_COMPARE',
          citations: [],
          result_data: {
            products: [
              {
                id: 'product-1',
                name: 'Wireless headphones',
                description: 'Over-ear',
                category: 'Audio',
                sku: 'HP-1',
                price_cents: 4999,
                stock_quantity: 3,
                max_purchase_quantity: 4,
              },
              {
                id: 'product-2',
                name: 'Wired headphones',
                description: null,
                category: 'Audio',
                sku: 'HP-2',
                price_cents: 2999,
                stock_quantity: 0,
                max_purchase_quantity: 2,
              },
            ],
          },
        }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'csrf-token' }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [] }) });

    render(<AssistantPage />);
    fireEvent.change(screen.getByLabelText('Message the shopping assistant'), {
      target: { value: 'compare headphones' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(
      await screen.findByRole('table', { name: 'Catalog fields returned for these products' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('row', { name: /Wireless headphones Audio ₹49\.99 In stock \(3\)/ })
    ).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'View product' })[0]).toHaveAttribute(
      'href',
      '/products/product-1'
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));

    fireEvent.click(screen.getAllByRole('button', { name: 'Add to cart' })[0]);

    expect(await screen.findByRole('status')).toHaveTextContent('Added to your cart.');
    expect(fetchMock).toHaveBeenCalledTimes(6);
    expect(fetchMock.mock.calls[5][0]).toBe('/api/cart/items');
    expect(fetchMock.mock.calls[5][1]).toEqual(
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': 'csrf-token' },
        body: JSON.stringify({ product_id: 'product-1', quantity: 1 }),
      })
    );
  });

  it('states when the catalog has no matching products and an answer is unverified', async () => {
    const fetchMock = global.fetch as jest.Mock;
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'csrf' }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          conversation_id: 'conversation-1',
          message_id: 'message-1',
          answer: 'I could not verify a matching item.',
          answerable: false,
          reason: 'NO_RESULTS',
          intent: 'PRODUCT_SEARCH',
          citations: [],
          result_data: { products: [] },
        }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => [] });

    render(<AssistantPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Find in-stock products under ₹5,000' }));

    expect(
      await screen.findByText('No matching products were returned from the catalog.')
    ).toBeInTheDocument();
    expect(
      screen.getByText('I couldn’t verify an answer from the available ShopSmart information.')
    ).toBeInTheDocument();
  });

  it('shows a thinking state while the assistant request is pending', async () => {
    const fetchMock = global.fetch as jest.Mock;
    let resolveChat: (response: { ok: boolean; json: () => Promise<unknown> }) => void = () => {};
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'csrf' }) })
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveChat = resolve;
          })
      )
      .mockResolvedValueOnce({ ok: true, json: async () => [] });

    render(<AssistantPage />);
    fireEvent.change(screen.getByLabelText('Message the shopping assistant'), {
      target: { value: 'Find headphones' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Checking the catalog, cart, and ShopSmart information…'
    );
    await act(async () => {
      resolveChat({
        ok: true,
        json: async () => ({
          conversation_id: 'conversation-1',
          message_id: 'message-1',
          answer: 'A grounded answer.',
          answerable: true,
          reason: null,
          intent: 'HELP',
          citations: [],
          result_data: null,
        }),
      });
    });

    expect(await screen.findByText('A grounded answer.')).toBeInTheDocument();
  });

  it('reports a cart conflict without claiming the item was added', async () => {
    const fetchMock = global.fetch as jest.Mock;
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'csrf-token' }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          conversation_id: 'conversation-1',
          message_id: 'message-1',
          answer: 'One product is available.',
          answerable: true,
          reason: null,
          intent: 'PRODUCT_SEARCH',
          citations: [],
          result_data: {
            products: [
              {
                id: 'product-1',
                name: 'Wireless headphones',
                description: null,
                sku: 'HP-1',
                price_cents: 4999,
                stock_quantity: 1,
              },
            ],
          },
        }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'csrf-token' }) })
      .mockResolvedValueOnce({ ok: false, status: 409 });

    render(<AssistantPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Find in-stock products under ₹5,000' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Add to cart' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The requested quantity is no longer available.'
    );
    expect(screen.queryByText('Added to your cart.')).not.toBeInTheDocument();
  });

  it('renders a deterministic greeting and starts a fresh chat', async () => {
    const fetchMock = global.fetch as jest.Mock;
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'csrf' }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          conversation_id: 'conversation-1',
          message_id: 'message-1',
          answer: 'Hi! I can help you find products.',
          answerable: true,
          reason: null,
          intent: 'GREETING',
          citations: [],
          result_data: null,
        }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => [] });

    render(<AssistantPage />);
    fireEvent.change(screen.getByLabelText('Message the shopping assistant'), {
      target: { value: 'hi' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('Hi! I can help you find products.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'New chat' }));
    expect(screen.queryByText('Hi! I can help you find products.')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'What can I help you find?' })).toBeInTheDocument();
  });

  it('renders only authoritative promotion results returned by the assistant', async () => {
    const fetchMock = global.fetch as jest.Mock;
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'csrf' }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          conversation_id: 'conversation-1',
          message_id: 'message-1',
          answer: 'I found 1 active offer.',
          answerable: true,
          reason: null,
          intent: 'PROMOTIONS',
          citations: [],
          result_data: {
            promotions: [
              {
                promotion_id: 'promotion-1',
                code: 'SAVE10',
                name: 'Laptop offer',
                description: 'Ten percent on laptops',
                promotion_type: 'percentage',
                value: 10,
                scope_type: 'category',
                scope_category: 'laptops',
                min_cart_total_cents: null,
                max_discount_cents: null,
              },
            ],
          },
        }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => [] });

    render(<AssistantPage />);
    fireEvent.click(screen.getByRole('button', { name: 'What offers are active?' }));

    expect(await screen.findByText('Laptop offer')).toBeInTheDocument();
    expect(screen.getByText('Code SAVE10')).toBeInTheDocument();
    expect(screen.getByText('10% off')).toBeInTheDocument();
  });

  it('maps an expired session separately from a service failure', async () => {
    const fetchMock = global.fetch as jest.Mock;
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'csrf' }) })
      .mockResolvedValueOnce({ ok: false, status: 401 });

    render(<AssistantPage />);
    fireEvent.change(screen.getByLabelText('Message the shopping assistant'), {
      target: { value: 'hi' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Please sign in to continue.');
  });

  it.each([
    [500, 'The assistant encountered an internal error. Please try again.'],
    [503, 'The assistant is temporarily unavailable.'],
  ])('maps HTTP %s to its distinct user-facing error', async (status, message) => {
    const fetchMock = global.fetch as jest.Mock;
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'csrf' }) })
      .mockResolvedValueOnce({ ok: false, status });

    render(<AssistantPage />);
    fireEvent.change(screen.getByLabelText('Message the shopping assistant'), {
      target: { value: 'hi' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(message);
  });

  it('restores the latest conversation and its structured commerce result', async () => {
    const fetchMock = global.fetch as jest.Mock;
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).includes('/messages')) {
        return {
          ok: true,
          json: async () => [
            {
              id: 'user-message',
              role: 'user',
              content: 'show products',
              citations: [],
              result_data: null,
            },
            {
              id: 'assistant-message',
              role: 'assistant',
              content: 'I found a product.',
              citations: [],
              result_data: {
                products: [
                  {
                    id: 'product-1',
                    name: 'Restored headphones',
                    description: null,
                    sku: 'HP-1',
                    price_cents: 4999,
                    stock_quantity: 2,
                  },
                ],
              },
            },
          ],
        };
      }
      return {
        ok: true,
        json: async () => [
          { id: 'conversation-1', title: 'show products', created_at: '2026-10-01' },
        ],
      };
    });

    render(<AssistantPage />);

    expect(await screen.findByText('Restored headphones')).toBeInTheDocument();
    expect(screen.getByText('₹49.99')).toBeInTheDocument();
  });
});
