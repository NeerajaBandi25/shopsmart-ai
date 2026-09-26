'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getCart, removeCartItem, type Cart } from '@/lib/cart-api';
import { CheckoutForm } from '@/components/CheckoutForm';

export function CheckoutFlow() {
  const [cart, setCart] = useState<Cart | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    setError('');
    getCart()
      .then((result) => {
        if (active) setCart(result);
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(cause instanceof Error ? cause.message : 'Your cart could not be loaded.');
        }
      });
    return () => {
      active = false;
    };
  }, [retry]);

  async function clearPurchasedItems() {
    if (!cart) return true;
    const results = await Promise.allSettled(
      cart.items.map((item) => removeCartItem(item.product_id))
    );
    const failed = results.some((result) => result.status === 'rejected');
    if (!failed) setCart({ items: [], subtotal: 0, currency: cart.currency });
    return failed;
  }

  if (error) {
    return (
      <div role="alert" className="space-y-3 border-y border-red-200 bg-red-50 px-5 py-6">
        <p className="text-sm text-red-700">{error}</p>
        <button
          type="button"
          onClick={() => setRetry((value) => value + 1)}
          className="font-semibold text-accent-700 underline underline-offset-4"
        >
          Try again
        </button>
      </div>
    );
  }

  if (!cart)
    return (
      <p role="status" className="text-sm text-ink-500">
        Loading your cart...
      </p>
    );

  return (
    <section className="rounded-tile border border-ink-100 bg-white p-5 shadow-tile sm:p-7">
      <CheckoutForm
        items={cart.items.map((item) => ({
          product_id: item.product_id,
          quantity: item.quantity,
          product_name: item.name,
        }))}
        onSuccess={clearPurchasedItems}
      />
      {cart.items.length > 0 && (
        <p className="mt-5 text-right text-sm font-semibold text-ink-900">
          Subtotal ${(cart.subtotal / 100).toFixed(2)}
        </p>
      )}
      {cart.items.length === 0 && (
        <Link
          href="/"
          className="mt-4 inline-block text-sm font-semibold text-accent-700 underline"
        >
          Browse products
        </Link>
      )}
    </section>
  );
}
