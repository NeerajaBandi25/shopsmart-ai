import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AssistantPage from './page';

jest.mock('@/app/authenticated-layout', () => {
  function MockAuthenticatedLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>;
  }

  return { __esModule: true, default: MockAuthenticatedLayout };
});

describe('shopping assistant page', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
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
    fireEvent.click(screen.getByRole('button', { name: 'Find in-stock products under $50' }));

    expect(await screen.findByText('Wireless headphones')).toBeInTheDocument();
    expect(screen.getByText('$49.99')).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
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
    expect(screen.getByText('$49.99')).toBeInTheDocument();
  });
});
