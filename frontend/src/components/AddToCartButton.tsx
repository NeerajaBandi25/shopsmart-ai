'use client';

import { useState } from 'react';
import { addCartItem } from '@/lib/cart-api';

interface AddToCartButtonProps {
  productId: string;
  stockQuantity: number;
  maxPurchaseQuantity: number;
}

export function AddToCartButton({
  productId,
  stockQuantity,
  maxPurchaseQuantity,
}: AddToCartButtonProps) {
  const maximum = Math.min(stockQuantity, maxPurchaseQuantity);
  const [quantity, setQuantity] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function handleAdd() {
    setIsSubmitting(true);
    setMessage('');
    setError('');
    try {
      await addCartItem(productId, quantity);
      setMessage('Added to cart.');
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : 'Could not add this item.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1 text-xs font-medium text-ink-500">
        Quantity
        <input
          aria-label="Quantity"
          type="number"
          min={1}
          max={maximum}
          value={quantity}
          onChange={(event) => setQuantity(Number(event.target.value))}
          disabled={maximum < 1 || isSubmitting}
          className="h-10 w-20 rounded-sm border border-ink-300 bg-white px-2 text-sm text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
        />
      </label>
      <button
        type="button"
        onClick={handleAdd}
        disabled={maximum < 1 || quantity < 1 || quantity > maximum || isSubmitting}
        className="h-10 rounded-sm bg-accent-700 px-4 text-sm font-semibold text-white transition-colors hover:bg-accent-800 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
      >
        {isSubmitting ? 'Adding...' : maximum < 1 ? 'Out of stock' : 'Add to cart'}
      </button>
      {message && (
        <p role="status" className="w-full text-sm text-leaf-700">
          {message}
        </p>
      )}
      {error && (
        <p role="alert" className="w-full text-sm text-status-error">
          {error}
        </p>
      )}
    </div>
  );
}
