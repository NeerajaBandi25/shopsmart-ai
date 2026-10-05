'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getCart, type Cart } from '@/lib/cart-api';
import { CheckoutForm } from '@/components/CheckoutForm';
import { useCommerceStore } from '@/lib/commerce-store';

export function CheckoutFlow({ onRedirect }: { onRedirect?: (url: string) => void } = {}) {
  const syncCartCount = useCommerceStore((state) => state.syncCartCount);
  const [cart, setCart] = useState<Cart | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [paymentCancelled, setPaymentCancelled] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setPaymentCancelled(params.get('payment') === 'cancelled');
  }, []);

  useEffect(() => {
    let active = true;
    setError('');
    getCart()
      .then((result) => {
        if (active) {
          setCart(result);
          syncCartCount(result);
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(cause instanceof Error ? cause.message : 'Your cart could not be loaded.');
        }
      });
    return () => {
      active = false;
    };
  }, [retry, syncCartCount]);

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
      {paymentCancelled && (
        <p
          className="mb-5 border-l-2 border-amber-500 bg-amber-50 px-4 py-3 text-sm text-ink-800"
          role="status"
        >
          Checkout was cancelled. Your cart is unchanged; payment status is confirmed only by the
          secure payment provider.
        </p>
      )}
      <CheckoutForm
        items={cart.items.map((item) => ({
          product_id: item.product_id,
          quantity: item.quantity,
          product_name: item.name,
          product_sku: item.sku,
          product_image_url: item.image_url,
          product_image_alt: item.image_alt,
          unit_price_cents: item.unit_price,
          line_total_cents: item.line_total,
        }))}
        couponCode={cart.coupon_code}
        quote={{
          subtotal_cents: cart.subtotal,
          discount_total_cents: cart.discount_total_cents,
          total_cents: cart.total_cents,
          promotions: cart.applied_promotions.map(({ name, discount_cents }) => ({
            name,
            discount_cents,
          })),
        }}
        onRedirect={onRedirect}
      />
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
