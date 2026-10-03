'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getCart, removeCartItem, type Cart } from '@/lib/cart-api';
import { CheckoutForm } from '@/components/CheckoutForm';
import { useCommerceStore } from '@/lib/commerce-store';

export function CheckoutFlow() {
  const syncCartCount = useCommerceStore((state) => state.syncCartCount);
  const clearPrivateCommerce = useCommerceStore((state) => state.clearPrivateCommerce);
  const [cart, setCart] = useState<Cart | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);

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

  async function clearPurchasedItems() {
    if (!cart) return true;
    const results = await Promise.allSettled(
      cart.items.map((item) => removeCartItem(item.product_id))
    );
    const failed = results.some((result) => result.status === 'rejected');
    if (!failed) {
      clearPrivateCommerce();
      setCart({
        ...cart,
        items: [],
        subtotal: 0,
        coupon_code: null,
        coupon_evaluation: null,
        applied_promotions: [],
        discount_total_cents: 0,
        total_cents: 0,
      });
    } else {
      try {
        syncCartCount(await getCart());
      } catch {
        // Preserve the existing order-success cleanup warning if refresh fails.
      }
    }
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
        onSuccess={clearPurchasedItems}
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
