'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getCart, removeCartItem, setCartItemQuantity, type Cart } from '@/lib/cart-api';

const priceFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
});

export function CartPage() {
  const [cart, setCart] = useState<Cart | null>(null);
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [error, setError] = useState('');
  const [busyProductId, setBusyProductId] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let currentRequest = true;
    setStatus('loading');
    setError('');
    getCart()
      .then((result) => {
        if (currentRequest) {
          setCart(result);
          setQuantities({});
          setStatus('success');
        }
      })
      .catch((cause: unknown) => {
        if (currentRequest) {
          setError(cause instanceof Error ? cause.message : 'Your cart could not be loaded.');
          setStatus('error');
        }
      });
    return () => {
      currentRequest = false;
    };
  }, [retry]);

  async function updateQuantity(productId: string, quantity: number) {
    setBusyProductId(productId);
    setError('');
    try {
      const updated = await setCartItemQuantity(productId, quantity);
      setCart(updated);
      setQuantities({});
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : 'Quantity could not be updated.');
    } finally {
      setBusyProductId(null);
    }
  }

  async function removeItem(productId: string) {
    setBusyProductId(productId);
    setError('');
    try {
      const updated = await removeCartItem(productId);
      setCart(updated);
      setQuantities({});
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : 'Item could not be removed.');
    } finally {
      setBusyProductId(null);
    }
  }

  return (
    <section aria-labelledby="cart-title" className="mx-auto max-w-5xl">
      <div className="mb-8 border-b border-ink-100 pb-6">
        <p className="text-xs font-semibold uppercase tracking-caps text-accent-700">
          Your selection
        </p>
        <h1 id="cart-title" className="mt-2 font-display text-display-md font-bold text-ink-900">
          Shopping cart
        </h1>
      </div>

      {status === 'loading' && (
        <p role="status" className="border-y border-ink-100 py-8 text-sm text-ink-500">
          Loading your cart...
        </p>
      )}

      {status === 'error' && (
        <div role="alert" className="border-y border-red-200 bg-red-50 px-5 py-6">
          <p className="font-medium text-ink-900">Your cart could not be loaded.</p>
          <p className="mt-1 text-sm text-ink-500">{error}</p>
          <button
            type="button"
            onClick={() => setRetry((count) => count + 1)}
            className="mt-4 rounded-sm bg-accent-700 px-4 py-2 text-sm font-semibold text-white hover:bg-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
          >
            Try again
          </button>
        </div>
      )}

      {status === 'success' && cart?.items.length === 0 && (
        <div className="border-y border-ink-100 py-10 text-center">
          <p className="font-display text-2xl font-bold text-ink-900">Your cart is empty.</p>
          <Link
            href="/"
            className="mt-4 inline-flex rounded-sm bg-accent-700 px-4 py-2 text-sm font-semibold text-white hover:bg-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
          >
            Browse products
          </Link>
        </div>
      )}

      {status === 'success' && cart && cart.items.length > 0 && (
        <>
          {error && (
            <p role="alert" className="mb-4 text-sm text-status-error">
              {error}
            </p>
          )}
          <div className="divide-y divide-ink-100 border-y border-ink-100">
            {cart.items.map((item) => {
              const quantity = quantities[item.product_id] ?? item.quantity;
              const maximum = Math.min(item.stock_quantity, item.max_purchase_quantity);
              const isBusy = busyProductId === item.product_id;
              return (
                <article
                  key={item.product_id}
                  className="grid gap-4 py-6 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
                >
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-caps text-ink-500">
                      SKU {item.sku}
                    </p>
                    <h2 className="mt-1 font-display text-xl font-bold text-ink-900">
                      {item.name}
                    </h2>
                    <p className="mt-1 text-sm text-ink-500">
                      {priceFormatter.format(item.unit_price / 100)} each
                    </p>
                  </div>
                  <div className="flex flex-wrap items-end gap-3 sm:justify-end">
                    <label className="flex flex-col gap-1 text-xs font-medium text-ink-500">
                      Quantity
                      <input
                        aria-label={`Quantity for ${item.name}`}
                        type="number"
                        min={1}
                        max={maximum}
                        value={quantity}
                        onChange={(event) =>
                          setQuantities((current) => ({
                            ...current,
                            [item.product_id]: Number(event.target.value),
                          }))
                        }
                        disabled={isBusy || maximum < 1}
                        className="h-10 w-20 rounded-sm border border-ink-300 bg-white px-2 text-sm text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() => updateQuantity(item.product_id, quantity)}
                      disabled={
                        isBusy || quantity < 1 || quantity > maximum || quantity === item.quantity
                      }
                      className="h-10 rounded-sm border border-ink-300 px-3 text-sm font-semibold text-ink-700 hover:bg-blush-50 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Update
                    </button>
                    <button
                      type="button"
                      onClick={() => removeItem(item.product_id)}
                      disabled={isBusy}
                      className="h-10 rounded-sm px-2 text-sm font-semibold text-accent-700 underline underline-offset-4 disabled:opacity-40"
                    >
                      Remove
                    </button>
                    <p className="min-w-24 text-right font-semibold text-ink-900">
                      {priceFormatter.format(item.line_total / 100)}
                    </p>
                  </div>
                </article>
              );
            })}
          </div>
          <div className="ml-auto flex max-w-sm items-baseline justify-between gap-6 py-6">
            <p className="text-sm font-medium text-ink-500">Subtotal</p>
            <p className="font-display text-2xl font-bold text-ink-900">
              {priceFormatter.format(cart.subtotal / 100)}
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-4 border-t border-ink-100 pt-5">
            <Link
              href="/checkout"
              className="rounded-sm bg-accent-700 px-5 py-3 text-sm font-semibold text-white hover:bg-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
            >
              Continue to checkout
            </Link>
          </div>
        </>
      )}
    </section>
  );
}
