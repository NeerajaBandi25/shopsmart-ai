'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { OrderSnapshot } from '@/components/commerce/OrderSnapshot';
import { getCart } from '@/lib/cart-api';
import { getOrder, retryPayment, type Order } from '@/lib/order-api';
import { useCommerceStore } from '@/lib/commerce-store';

type Verification = 'checking' | 'paid' | 'failed' | 'cancelled' | 'pending' | 'error';

export default function CheckoutCompletePage({
  onRedirect,
}: { onRedirect?: (url: string) => void } = {}) {
  const [order, setOrder] = useState<Order | null>(null);
  const [verification, setVerification] = useState<Verification>('checking');
  const [message, setMessage] = useState('Checking the verified payment status…');
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState('');
  const syncCartCount = useCommerceStore((state) => state.syncCartCount);

  useEffect(() => {
    let active = true;
    const orderId = new URLSearchParams(window.location.search).get('order_id');
    if (!orderId || !/^[0-9a-f-]{36}$/i.test(orderId)) {
      setVerification('error');
      setMessage(
        'We could not verify this order. Check your order history for its current status.'
      );
      return () => {
        active = false;
      };
    }

    async function verifyPayment() {
      try {
        let latest: Order | null = null;
        for (let attempt = 0; attempt < 8; attempt += 1) {
          latest = await getOrder(orderId);
          if (!active) return;
          setOrder(latest);
          if (latest.payment_status === 'succeeded') {
            setVerification('paid');
            setMessage('Payment confirmed. Your order is now in your order history.');
            try {
              window.sessionStorage.removeItem('shopsmart.checkout.idempotency.v1');
            } catch {
              // Storage may be disabled; backend idempotency remains authoritative.
            }
            try {
              syncCartCount(await getCart());
            } catch {
              // Payment state is already verified; a stale local cart count is recoverable on refresh.
            }
            return;
          }
          if (latest.payment_status === 'failed') {
            setVerification('failed');
            setMessage('The payment was not completed. Your cart is still available to try again.');
            return;
          }
          if (latest.payment_status === 'cancelled') {
            setVerification('cancelled');
            setMessage('Checkout was cancelled. Your cart is unchanged.');
            try {
              window.sessionStorage.removeItem('shopsmart.checkout.idempotency.v1');
            } catch {
              // A future checkout gets a new key from its cart snapshot when storage is available.
            }
            return;
          }
          if (latest.payment_status === 'requires_action') {
            setVerification('pending');
            setMessage('Payment has not been confirmed. Continue securely when you are ready.');
            return;
          }
          if (attempt < 7) await new Promise((resolve) => window.setTimeout(resolve, 1500));
        }
        if (active) {
          setVerification('pending');
          setMessage('Payment confirmation is still processing. Check your order history shortly.');
        }
      } catch {
        if (active) {
          setVerification('error');
          setMessage('We could not check payment status. Your order history remains available.');
        }
      }
    }

    void verifyPayment();
    return () => {
      active = false;
    };
  }, [syncCartCount]);

  async function handleRetryPayment() {
    if (!order || retrying) return;
    setRetrying(true);
    setRetryError('');
    try {
      const updatedOrder = await retryPayment(order.id);
      const checkoutUrl = new URL(updatedOrder.checkout_url || '');
      if (checkoutUrl.protocol !== 'https:' || checkoutUrl.hostname !== 'checkout.stripe.com') {
        throw new Error('Payment destination could not be verified');
      }
      (onRedirect || ((url: string) => window.location.assign(url)))(checkoutUrl.toString());
    } catch {
      setRetryError('We could not reopen secure payment. Your existing order is still available.');
      setRetrying(false);
    }
  }

  return (
    <main className="mx-auto min-h-[60vh] max-w-3xl space-y-6 px-5 py-12 sm:px-8">
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-caps text-accent-700">Checkout</p>
        <h1 className="font-display text-display-sm font-bold text-ink-900">
          {verification === 'paid' ? 'Payment confirmed' : 'Payment status'}
        </h1>
        <p className="text-sm leading-relaxed text-ink-600" role="status" aria-live="polite">
          {message}
        </p>
      </header>

      {order && <OrderSnapshot order={order} title="Your order" />}

      {retryError && (
        <p className="text-sm text-red-700" role="alert">
          {retryError}
        </p>
      )}

      {verification === 'checking' && (
        <p className="text-sm text-ink-500" role="status">
          Verifying with ShopSmart…
        </p>
      )}

      <nav className="flex flex-wrap gap-5 text-sm font-semibold">
        <Link href="/orders" className="text-accent-700 underline underline-offset-4">
          View order history
        </Link>
        {(verification === 'failed' ||
          (verification === 'pending' &&
            order?.payment_status !== 'cancelled' &&
            order?.payment_status !== 'succeeded')) && (
          <button
            type="button"
            onClick={handleRetryPayment}
            disabled={retrying}
            className="text-accent-700 underline underline-offset-4 disabled:opacity-60"
          >
            {retrying
              ? 'Opening secure checkout…'
              : verification === 'failed'
                ? 'Retry payment for this order'
                : 'Continue secure checkout'}
          </button>
        )}
        {verification === 'cancelled' && (
          <Link href="/checkout" className="text-accent-700 underline underline-offset-4">
            Return to checkout
          </Link>
        )}
        <Link href="/" className="text-accent-700 underline underline-offset-4">
          Continue shopping
        </Link>
      </nav>
    </main>
  );
}
