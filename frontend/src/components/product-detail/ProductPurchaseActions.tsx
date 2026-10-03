'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { addCartItem } from '@/lib/cart-api';
import { useCommerceStore } from '@/lib/commerce-store';

interface ProductPurchaseActionsProps {
  productId: string;
  stockQuantity: number;
  maxPurchaseQuantity: number;
}

export function ProductPurchaseActions({
  productId,
  stockQuantity,
  maxPurchaseQuantity,
}: ProductPurchaseActionsProps) {
  const maximum = Math.max(0, Math.min(stockQuantity, maxPurchaseQuantity));
  const router = useRouter();
  const syncCartCount = useCommerceStore((state) => state.syncCartCount);
  const [quantity, setQuantity] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function purchase(goToCheckout: boolean) {
    if (maximum < 1 || quantity < 1 || quantity > maximum || isSubmitting) return;
    setIsSubmitting(true);
    setMessage('');
    setError('');
    try {
      const cart = await addCartItem(productId, quantity);
      syncCartCount(cart);
      if (goToCheckout) {
        router.push('/checkout');
      } else {
        setMessage('Added to cart.');
      }
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : 'Could not add this item.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mt-8 space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="product-quantity" className="text-xs font-medium text-ink-500">
            Quantity
          </label>
          <div className="flex h-10 items-center border border-ink-300">
            <button
              type="button"
              aria-label="Decrease quantity"
              onClick={() => setQuantity((current) => Math.max(1, current - 1))}
              disabled={quantity <= 1 || maximum < 1 || isSubmitting}
              className="h-full w-10 text-lg text-ink-800 hover:bg-blush-50 disabled:opacity-40"
            >
              −
            </button>
            <input
              id="product-quantity"
              aria-label="Quantity"
              type="number"
              min={1}
              max={maximum}
              value={quantity}
              onChange={(event) => setQuantity(Number(event.target.value))}
              disabled={maximum < 1 || isSubmitting}
              className="h-full w-12 border-x border-ink-300 text-center text-sm text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-500"
            />
            <button
              type="button"
              aria-label="Increase quantity"
              onClick={() => setQuantity((current) => Math.min(maximum, current + 1))}
              disabled={quantity >= maximum || isSubmitting}
              className="h-full w-10 text-lg text-ink-800 hover:bg-blush-50 disabled:opacity-40"
            >
              +
            </button>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void purchase(false)}
          disabled={maximum < 1 || quantity < 1 || quantity > maximum || isSubmitting}
          className="h-10 bg-accent-700 px-4 text-sm font-semibold text-white transition-colors hover:bg-accent-800 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
        >
          {isSubmitting ? 'Adding...' : maximum < 1 ? 'Out of stock' : 'Add to cart'}
        </button>
        <button
          type="button"
          onClick={() => void purchase(true)}
          disabled={maximum < 1 || quantity < 1 || quantity > maximum || isSubmitting}
          className="h-10 border border-ink-300 px-4 text-sm font-semibold text-ink-800 hover:bg-blush-50 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
        >
          Buy now
        </button>
      </div>
      {message && (
        <p role="status" className="text-sm text-leaf-700">
          {message}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-status-error">
          {error}
        </p>
      )}
    </div>
  );
}
