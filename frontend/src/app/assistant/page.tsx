'use client';

import { FormEvent, useEffect, useState } from 'react';
import AuthenticatedLayout from '@/app/authenticated-layout';

type Product = {
  id: string;
  name: string;
  description: string | null;
  sku: string;
  price_cents: number;
  stock_quantity: number;
};
type Citation = {
  citation_id: string;
  source_label: string;
  page_number: number | null;
  chunk_index: number;
};
type ChatResult = {
  conversation_id: string;
  message_id: string;
  answer: string;
  answerable: boolean;
  reason: string | null;
  intent: string;
  citations: Citation[];
  result_data: {
    products?: Product[];
    cart?: { items: { name: string; quantity: number; line_total: number }[]; subtotal: number };
    orders?: { id: string; status: string; total_cents: number; created_at: string }[];
  } | null;
};
type Message = {
  role: 'user' | 'assistant';
  content: string;
  result?: ChatResult;
  citations?: Citation[];
};
type Conversation = { id: string; title: string; created_at: string };
type StoredMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[];
  result_data: ChatResult['result_data'];
};

const suggestions = [
  'Find in-stock products under $50',
  'What offers are active?',
  "What's in my cart?",
  'What is the return policy?',
];

function money(cents: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(cents / 100);
}

async function fetchConversations(): Promise<Conversation[]> {
  const response = await fetch('/api/ai/conversations', { credentials: 'include' });
  if (!response.ok)
    throw new Error(apiErrorMessage(response, 'Could not load recent conversations.'));
  return response.json();
}

function apiErrorMessage(response: Response, fallback: string): string {
  if (response.status === 401) return 'Please sign in to continue.';
  if (response.status === 403) return 'You are not allowed to use this conversation.';
  if (response.status === 404) return 'This conversation could not be found.';
  if (response.status === 422) return 'Please check your message and try again.';
  if (response.status === 503) return 'The assistant is temporarily unavailable.';
  if (response.status >= 500)
    return 'The assistant encountered an internal error. Please try again.';
  return fallback;
}

export default function AssistantPage() {
  const [question, setQuestion] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchConversations()
      .then((items) => {
        setConversations(items);
        if (items.length > 0) void openConversation(items[0].id);
      })
      .catch(() => setError('Could not load recent conversations.'));
  }, []);

  async function ask(text: string) {
    const submitted = text.trim();
    if (!submitted || busy) return;
    setQuestion('');
    setBusy(true);
    setError(null);
    setMessages((items) => [...items, { role: 'user', content: submitted }]);
    try {
      const csrfResponse = await fetch('/api/auth/csrf', { credentials: 'include' });
      if (!csrfResponse.ok) throw new Error('Please sign in to continue.');
      const { csrf_token: csrfToken } = await csrfResponse.json();
      const response = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        credentials: 'include',
        body: JSON.stringify({ question: submitted, conversation_id: conversationId }),
      });
      if (!response.ok)
        throw new Error(apiErrorMessage(response, 'The assistant is temporarily unavailable.'));
      const result: ChatResult = await response.json();
      setConversationId(result.conversation_id);
      setMessages((items) => [...items, { role: 'assistant', content: result.answer, result }]);
      void fetchConversations()
        .then(setConversations)
        .catch(() => setError('Could not refresh recent conversations.'));
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'The assistant is temporarily unavailable.'
      );
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void ask(question);
  }

  function newConversation() {
    setConversationId(null);
    setMessages([]);
    setError(null);
  }

  async function openConversation(id: string) {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/ai/conversations/${encodeURIComponent(id)}/messages`, {
        credentials: 'include',
      });
      if (!response.ok)
        throw new Error(apiErrorMessage(response, 'Could not load this conversation.'));
      const stored: StoredMessage[] = await response.json();
      setConversationId(id);
      setMessages(
        stored.map((message) => ({
          role: message.role,
          content: message.content,
          citations: message.citations,
          result: message.result_data
            ? {
                conversation_id: id,
                message_id: message.id,
                answer: message.content,
                answerable: true,
                reason: null,
                intent: 'HISTORY',
                citations: message.citations,
                result_data: message.result_data,
              }
            : undefined,
        }))
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not load this conversation.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthenticatedLayout>
      <div className="mx-auto flex min-h-[calc(100vh-9rem)] max-w-5xl flex-col">
        <header className="flex items-center justify-between border-b border-ink-100 pb-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-caps text-accent-600">
              ShopSmart
            </p>
            <h1 className="font-display text-3xl font-bold text-ink-900">Shopping assistant</h1>
          </div>
          <button
            type="button"
            onClick={newConversation}
            className="rounded border border-ink-200 px-3 py-2 text-sm font-semibold text-ink-700 hover:bg-white"
          >
            New chat
          </button>
        </header>

        {conversations.length > 0 && (
          <nav
            aria-label="Recent conversations"
            className="flex gap-2 overflow-x-auto border-b border-ink-100 py-3"
          >
            {conversations.map((conversation) => (
              <button
                key={conversation.id}
                type="button"
                onClick={() => void openConversation(conversation.id)}
                disabled={busy}
                aria-current={conversation.id === conversationId ? 'true' : undefined}
                className="max-w-56 shrink-0 truncate rounded border border-ink-200 px-3 py-2 text-left text-sm text-ink-700 hover:bg-white disabled:opacity-50"
              >
                {conversation.title || 'ShopSmart conversation'}
              </button>
            ))}
          </nav>
        )}

        <section aria-live="polite" className="flex-1 space-y-7 py-7">
          {messages.length === 0 ? (
            <div className="py-8">
              <h2 className="font-display text-2xl font-semibold text-ink-900">
                What can I help you find?
              </h2>
              <p className="mt-2 text-ink-500">
                Search products, check your cart or orders, and get answers from ShopSmart policies.
              </p>
              <div className="mt-6 flex flex-wrap gap-2">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => void ask(suggestion)}
                    disabled={busy}
                    className="rounded-full border border-ink-200 bg-white px-4 py-2 text-sm text-ink-700 hover:border-accent-500 disabled:opacity-50"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message, index) => (
              <article key={`${index}-${message.role}`} className="space-y-4">
                <div
                  className={message.role === 'user' ? 'ml-auto max-w-3xl text-right' : 'max-w-4xl'}
                >
                  <p className="mb-1 text-xs font-semibold uppercase tracking-caps text-ink-500">
                    {message.role === 'user' ? 'You' : 'ShopSmart assistant'}
                  </p>
                  <p
                    className={
                      message.role === 'user'
                        ? 'inline-block rounded-lg bg-ink-900 px-4 py-3 text-left text-white'
                        : 'whitespace-pre-wrap text-ink-900'
                    }
                  >
                    {message.content}
                  </p>
                </div>
                {message.result?.result_data?.products && (
                  <div className="grid gap-3 sm:grid-cols-2">
                    {message.result.result_data.products.map((product) => (
                      <div
                        key={product.id}
                        className="rounded-md border border-ink-200 bg-white p-4"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <h3 className="font-semibold text-ink-900">{product.name}</h3>
                          <span className="shrink-0 font-semibold text-ink-900">
                            {money(product.price_cents)}
                          </span>
                        </div>
                        {product.description && (
                          <p className="mt-2 text-sm text-ink-600">{product.description}</p>
                        )}
                        <p className="mt-3 text-xs text-ink-500">
                          SKU {product.sku} · {product.stock_quantity} in stock
                        </p>
                        <button
                          type="button"
                          disabled={busy || product.stock_quantity < 1}
                          onClick={() => void ask(`Add to cart ${product.name}`)}
                          className="mt-4 rounded bg-accent-600 px-3 py-2 text-sm font-semibold text-white hover:bg-accent-700 disabled:opacity-50"
                        >
                          Add to cart
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                {message.result?.result_data?.cart && (
                  <div className="max-w-3xl border-l-2 border-accent-500 pl-4 text-sm text-ink-700">
                    {message.result.result_data.cart.items.length === 0 ? (
                      <p>Your cart is empty.</p>
                    ) : (
                      <>
                        {message.result.result_data.cart.items.map((item, itemIndex) => (
                          <p key={`${item.name}-${itemIndex}`}>
                            {item.quantity} × {item.name} · {money(item.line_total)}
                          </p>
                        ))}
                        <p className="mt-2 font-semibold">
                          Subtotal {money(message.result.result_data.cart.subtotal)}
                        </p>
                      </>
                    )}
                  </div>
                )}
                {message.result?.result_data?.orders && (
                  <div className="space-y-2 text-sm text-ink-700">
                    {message.result.result_data.orders.map((order) => (
                      <p key={order.id}>
                        Order {order.id.slice(0, 8)} · {order.status} · {money(order.total_cents)}
                      </p>
                    ))}
                  </div>
                )}
                {!!(message.result?.citations.length || message.citations?.length) && (
                  <ul className="space-y-1 text-xs text-ink-500">
                    {(message.result?.citations ?? message.citations ?? []).map((citation) => (
                      <li key={citation.citation_id}>
                        Source: {citation.source_label}
                        {citation.page_number ? `, page ${citation.page_number}` : ''}
                      </li>
                    ))}
                  </ul>
                )}
              </article>
            ))
          )}
          {busy && (
            <p role="status" className="text-sm text-ink-500">
              Checking ShopSmart...
            </p>
          )}
          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
        </section>

        <form onSubmit={submit} className="sticky bottom-0 border-t border-ink-100 bg-gray-50 py-4">
          <div className="flex gap-3">
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              aria-label="Message the shopping assistant"
              placeholder="Ask about products, your cart, orders, or ShopSmart policies"
              className="min-w-0 flex-1 rounded-md border border-ink-200 bg-white px-4 py-3 text-ink-900 outline-none focus:border-accent-600"
            />
            <button
              type="submit"
              disabled={busy || !question.trim()}
              className="rounded-md bg-ink-900 px-5 py-3 font-semibold text-white hover:bg-ink-700 disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </form>
      </div>
    </AuthenticatedLayout>
  );
}
