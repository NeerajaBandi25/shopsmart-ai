'use client';

import Link from 'next/link';
import { useRef, useState } from 'react';
import { checkoutOrder, type CheckoutItem, type Order } from '@/lib/order-api';

export interface CheckoutLine extends CheckoutItem {
  product_name?: string;
}

interface CheckoutFormProps {
  items: CheckoutLine[];
  onSuccess?: (order: Order) => void;
}

function createIdempotencyKey(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function CheckoutForm({ items, onSuccess }: CheckoutFormProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [placedOrder, setPlacedOrder] = useState<Order | null>(null);
  const idempotencyKey = useRef<string | null>(null);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!items.length || submitting) return;
    setSubmitting(true);
    setError(null);
    idempotencyKey.current ??= createIdempotencyKey();
    try {
      const order = await checkoutOrder(
        items.map(({ product_id, quantity }) => ({ product_id, quantity })),
        idempotencyKey.current
      );
      setPlacedOrder(order);
      onSuccess?.(order);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Checkout could not be completed.');
    } finally {
      setSubmitting(false);
    }
  };

  if (placedOrder) {
    return (
      <section className="space-y-4" aria-live="polite">
        <p className="font-semibold text-leaf-700" role="status">
          Order placed successfully.
        </p>
        <p className="text-sm text-ink-500">Order #{placedOrder.id}</p>
        <Link href="/orders" className="font-medium text-accent-700 underline underline-offset-4">
          View order history
        </Link>
      </section>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      {error && (
        <p className="text-sm text-red-700" role="alert">
          {error}
        </p>
      )}
      {!items.length ? (
        <p className="text-sm text-ink-500" role="status">
          There are no items ready for checkout.
        </p>
      ) : (
        <ul className="divide-y divide-ink-100">
          {items.map((item) => (
            <li key={item.product_id} className="flex flex-wrap justify-between gap-2 py-4">
              <span className="font-medium text-ink-900">
                {item.product_name || item.product_id}
              </span>
              <span className="text-sm text-ink-500">Quantity {item.quantity}</span>
            </li>
          ))}
        </ul>
      )}
      <button
        type="submit"
        disabled={!items.length || submitting}
        className="rounded-md bg-accent-700 px-5 py-3 font-semibold text-white transition-colors hover:bg-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? 'Placing order...' : 'Place order'}
      </button>
    </form>
  );
}
