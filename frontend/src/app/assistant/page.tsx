'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCommerceStore } from '@/lib/commerce-store';
import AuthenticatedLayout from '@/app/authenticated-layout';
import { formatInr } from '@/lib/currency';
import CommerceResults, {
  ProductResult,
  PromotionResult,
} from '@/components/assistant/CommerceResults';

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
    comparison?: boolean;
    navigation?: string;
    buying_brief?: { product_id: string; name: string; reasons: string[] }[];
    products?: ProductResult[];
    cart?: {
      items: { name: string; quantity: number; line_total: number }[];
      subtotal: number;
      discount_total_cents?: number;
      total_cents?: number;
    };
    promotions?: PromotionResult[];
    coupon_evaluation?: { eligible: boolean; reason_code: string; discount_cents: number };
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
  'Show me the best laptops under ₹60,000',
  'Find in-stock products under ₹5,000',
  'What offers are active?',
  "What's in my cart?",
  'What is the return policy?',
];

function money(cents: number) {
  return formatInr(cents);
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
  const router = useRouter();
  const [question, setQuestion] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addingProductId, setAddingProductId] = useState<string | null>(null);
  const [cartAction, setCartAction] = useState<{
    resultId: string;
    kind: 'success' | 'error';
    message: string;
  } | null>(null);

  useEffect(() => {
    // PDP and command palette pass shopper wording; it remains editable until submitted.
    const contextualQuestion = new URLSearchParams(window.location.search).get('q');
    if (contextualQuestion) setQuestion(contextualQuestion.slice(0, 1000));
    void fetchConversations()
      .then((items) => {
        setConversations(items);
        if (items.length > 0 && !contextualQuestion) void openConversation(items[0].id);
      })
      .catch(() => setError('Could not load recent conversations.'));
  }, []);

  async function ask(text: string) {
    const submitted = text.trim();
    if (!submitted || busy) return;
    setQuestion('');
    setBusy(true);
    setError(null);
    setCartAction(null);
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
      if (result.result_data?.cart)
        useCommerceStore.getState().syncCartCount(result.result_data.cart);
      setConversationId(result.conversation_id);
      setMessages((items) => [...items, { role: 'assistant', content: result.answer, result }]);
      // Only the explicit checkout intent may navigate; arbitrary model URLs are ignored.
      if (result.intent === 'CHECKOUT' && result.result_data?.navigation === '/checkout')
        router.push('/checkout');
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

  async function addToCart(productId: string, resultId: string) {
    setAddingProductId(productId);
    setCartAction(null);
    try {
      const csrfResponse = await fetch('/api/auth/csrf', { credentials: 'include' });
      if (!csrfResponse.ok) {
        throw new Error(
          csrfResponse.status === 401
            ? 'Please sign in to add items to your cart.'
            : 'Could not authorize this cart update. Please try again.'
        );
      }
      const { csrf_token: csrfToken } = await csrfResponse.json();
      const response = await fetch('/api/cart/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        credentials: 'include',
        body: JSON.stringify({ product_id: productId, quantity: 1 }),
      });
      if (!response.ok) {
        const message =
          response.status === 401
            ? 'Please sign in to add items to your cart.'
            : response.status === 404
              ? 'This product is no longer available.'
              : response.status === 409
                ? 'The requested quantity is no longer available.'
                : response.status >= 500
                  ? 'The cart is temporarily unavailable. Please try again.'
                  : 'Could not add this product to your cart. Please try again.';
        throw new Error(message);
      }
      setCartAction({ resultId, kind: 'success', message: 'Added to your cart.' });
      const cart = await response.json();
      if (cart?.items) useCommerceStore.getState().syncCartCount(cart);
    } catch (reason) {
      setCartAction({
        resultId,
        kind: 'error',
        message: reason instanceof Error ? reason.message : 'Could not update your cart.',
      });
    } finally {
      setAddingProductId(null);
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
    setCartAction(null);
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
      <div className="mx-auto flex min-h-[calc(100vh-9rem)] max-w-5xl flex-col px-4 sm:px-6">
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

        <section aria-live="polite" className="flex-1 space-y-7 py-5 sm:py-7">
          {messages.length === 0 ? (
            <div className="py-8">
              <h2 className="font-display text-2xl font-semibold text-ink-900">
                What can I help you find?
              </h2>
              <p className="mt-2 max-w-2xl text-ink-600">
                Browse catalog results, compare returned details, check your cart or orders, and get
                answers grounded in ShopSmart policies.
              </p>
              <div className="mt-6 grid gap-2 sm:flex sm:flex-wrap">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => void ask(suggestion)}
                    disabled={busy}
                    className="min-h-11 rounded border border-ink-200 bg-white px-4 py-2 text-left text-sm text-ink-700 hover:border-accent-500 disabled:opacity-50 sm:text-center"
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
                {message.result?.result_data && (
                  <CommerceResults
                    resultId={message.result.message_id}
                    products={message.result.result_data.products}
                    promotions={message.result.result_data.promotions}
                    addingProductId={addingProductId}
                    cartAction={cartAction}
                    onAddToCart={(productId, resultId) => void addToCart(productId, resultId)}
                    comparison={
                      message.result.result_data.comparison ||
                      message.result.intent === 'PRODUCT_COMPARE'
                    }
                    onCompare={() => void ask('Compare the first two')}
                  />
                )}
                {message.result?.result_data?.buying_brief && (
                  <section aria-label="AI buying brief" className="grid gap-3 sm:grid-cols-2">
                    {message.result.result_data.buying_brief.map((brief) => (
                      <div
                        key={brief.product_id}
                        className="rounded-xl border border-accent-100 bg-white p-4"
                      >
                        <h3 className="font-semibold text-ink-900">{brief.name}</h3>
                        <ul className="mt-2 space-y-1 text-sm text-ink-600">
                          {brief.reasons.map((reason) => (
                            <li key={reason}>{reason}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </section>
                )}
                {message.result?.result_data?.navigation === '/checkout' && (
                  <Link
                    href="/checkout"
                    className="inline-flex min-h-11 items-center rounded-lg bg-accent-700 px-4 text-sm font-semibold text-white"
                  >
                    Continue to checkout
                  </Link>
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
                        {(message.result.result_data.cart.discount_total_cents ?? 0) > 0 && (
                          <p className="mt-1 text-leaf-700">
                            Discount -
                            {money(message.result.result_data.cart.discount_total_cents ?? 0)}
                          </p>
                        )}
                        {message.result.result_data.cart.total_cents !== undefined && (
                          <p className="mt-1 font-semibold">
                            Total {money(message.result.result_data.cart.total_cents)}
                          </p>
                        )}
                      </>
                    )}
                  </div>
                )}
                {message.result?.result_data?.coupon_evaluation && (
                  <p className="max-w-3xl text-sm font-medium text-ink-700" role="status">
                    {message.result.result_data.coupon_evaluation.eligible
                      ? `Eligible coupon: ${money(message.result.result_data.coupon_evaluation.discount_cents)} off before offer selection.`
                      : 'No eligible coupon was found for the current cart.'}
                  </p>
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
                {message.result && !message.result.answerable && (
                  <p role="status" className="max-w-3xl text-sm text-ink-600">
                    I couldn’t verify an answer from the available ShopSmart information.
                  </p>
                )}
              </article>
            ))
          )}
          {busy && (
            <p role="status" className="text-sm text-ink-600">
              Checking the catalog, cart, and ShopSmart information…
            </p>
          )}
          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
        </section>

        <form
          onSubmit={submit}
          className="sticky bottom-0 border-t border-ink-100 bg-gray-50 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]"
        >
          <div className="flex gap-2 sm:gap-3">
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              aria-label="Message the shopping assistant"
              placeholder="Ask about products, your cart, orders, or ShopSmart policies"
              className="min-w-0 min-h-11 flex-1 rounded border border-ink-200 bg-white px-3 py-2 text-ink-900 outline-none focus:border-accent-600 sm:px-4"
            />
            <button
              type="submit"
              disabled={busy || !question.trim()}
              className="min-h-11 shrink-0 rounded bg-ink-900 px-4 py-2 font-semibold text-white hover:bg-ink-700 disabled:opacity-50 sm:px-5"
            >
              Send
            </button>
          </div>
        </form>
      </div>
    </AuthenticatedLayout>
  );
}
