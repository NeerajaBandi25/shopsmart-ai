'use client';

import Link from 'next/link';
import Image from 'next/image';
import { useRef, useState } from 'react';
import {
  checkoutOrder,
  type CheckoutItem,
  type DeliveryAddress,
  type Order,
} from '@/lib/order-api';
import { OrderSnapshot } from '@/components/commerce/OrderSnapshot';
import { formatInr } from '@/lib/currency';

export interface CheckoutLine extends CheckoutItem {
  product_name?: string;
  product_sku?: string;
  product_image_url?: string | null;
  product_image_alt?: string | null;
  unit_price_cents?: number;
  line_total_cents?: number;
}

export interface CheckoutQuote {
  subtotal_cents: number;
  discount_total_cents: number;
  total_cents: number;
  promotions: { name: string; discount_cents: number }[];
}

interface CheckoutFormProps {
  items: CheckoutLine[];
  couponCode?: string | null;
  quote?: CheckoutQuote;
  onSuccess?: (order: Order) => void | Promise<boolean | void>;
}

function createIdempotencyKey(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function CheckoutForm({ items, couponCode, quote, onSuccess }: CheckoutFormProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [placedOrder, setPlacedOrder] = useState<Order | null>(null);
  const [cartCleanupWarning, setCartCleanupWarning] = useState(false);
  const [deliveryAddress, setDeliveryAddress] = useState<DeliveryAddress>({
    recipient_name: '',
    phone: '',
    address_line1: '',
    address_line2: '',
    city: '',
    region: '',
    postal_code: '',
    country_code: 'IN',
  });
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
        idempotencyKey.current,
        couponCode,
        { ...deliveryAddress, address_line2: deliveryAddress.address_line2 || null }
      );
      setPlacedOrder(order);
      setCartCleanupWarning((await onSuccess?.(order)) === true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Checkout could not be completed.');
    } finally {
      setSubmitting(false);
    }
  };

  if (placedOrder) {
    return (
      <section className="space-y-4" aria-live="polite">
        <p
          className="border-l-2 border-leaf-600 bg-leaf-50 px-4 py-3 text-sm leading-relaxed text-leaf-800"
          role="status"
        >
          Delivery details are recorded for this local demo. No payment is collected, and no
          delivery service or date is provided.
        </p>
        {cartCleanupWarning && (
          <p role="alert" className="text-sm text-status-error">
            Your order was placed, but the cart could not be fully cleared. Review your cart.
          </p>
        )}
        <OrderSnapshot order={placedOrder} title="Order recorded" />
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
        <>
          <ul className="divide-y divide-ink-100">
            {items.map((item) => (
              <li key={item.product_id} className="flex flex-wrap justify-between gap-3 py-4">
                <div className="flex min-w-0 items-start gap-4">
                  {item.product_image_url && (
                    <div className="relative aspect-square w-16 shrink-0 overflow-hidden bg-sand-100">
                      <Image
                        src={item.product_image_url}
                        alt={
                          item.product_image_alt ||
                          `Illustration of ${item.product_name || 'product'}`
                        }
                        fill
                        sizes="64px"
                        className="object-contain p-1"
                      />
                    </div>
                  )}
                  <div className="min-w-0">
                    <p className="break-words font-medium text-ink-900">
                      {item.product_name || 'Product'}
                    </p>
                    {item.product_sku && (
                      <p className="mt-1 text-xs text-ink-500">SKU {item.product_sku}</p>
                    )}
                    <p className="mt-1 text-sm text-ink-500">
                      Quantity {item.quantity}
                      {typeof item.unit_price_cents === 'number' &&
                        ` · ${formatInr(item.unit_price_cents)} each`}
                    </p>
                  </div>
                </div>
                {typeof item.line_total_cents === 'number' && (
                  <p className="font-semibold tabular-nums text-ink-900">
                    {formatInr(item.line_total_cents)}
                  </p>
                )}
              </li>
            ))}
          </ul>
          <fieldset className="space-y-4 border-y border-ink-100 py-5">
            <legend className="px-0 font-display text-lg font-bold text-ink-900">
              Delivery address
            </legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
                Recipient name
                <input
                  autoComplete="name"
                  required
                  maxLength={120}
                  value={deliveryAddress.recipient_name}
                  onChange={(event) =>
                    setDeliveryAddress((current) => ({
                      ...current,
                      recipient_name: event.target.value,
                    }))
                  }
                  className="h-11 rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                />
              </label>
              <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
                Phone
                <input
                  type="tel"
                  autoComplete="tel"
                  required
                  pattern="\+?[0-9][0-9 ()\-]{6,18}"
                  maxLength={20}
                  value={deliveryAddress.phone}
                  onChange={(event) =>
                    setDeliveryAddress((current) => ({ ...current, phone: event.target.value }))
                  }
                  className="h-11 rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                />
              </label>
              <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700 sm:col-span-2">
                Address line 1
                <input
                  autoComplete="address-line1"
                  required
                  minLength={4}
                  maxLength={200}
                  value={deliveryAddress.address_line1}
                  onChange={(event) =>
                    setDeliveryAddress((current) => ({
                      ...current,
                      address_line1: event.target.value,
                    }))
                  }
                  className="h-11 rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                />
              </label>
              <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700 sm:col-span-2">
                Address line 2 (optional)
                <input
                  autoComplete="address-line2"
                  maxLength={200}
                  value={deliveryAddress.address_line2 || ''}
                  onChange={(event) =>
                    setDeliveryAddress((current) => ({
                      ...current,
                      address_line2: event.target.value,
                    }))
                  }
                  className="h-11 rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                />
              </label>
              <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
                City
                <input
                  autoComplete="address-level2"
                  required
                  maxLength={100}
                  value={deliveryAddress.city}
                  onChange={(event) =>
                    setDeliveryAddress((current) => ({ ...current, city: event.target.value }))
                  }
                  className="h-11 rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                />
              </label>
              <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
                State or region
                <input
                  autoComplete="address-level1"
                  required
                  maxLength={100}
                  value={deliveryAddress.region}
                  onChange={(event) =>
                    setDeliveryAddress((current) => ({ ...current, region: event.target.value }))
                  }
                  className="h-11 rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                />
              </label>
              <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
                Postal code
                <input
                  autoComplete="postal-code"
                  required
                  pattern="[A-Za-z0-9\- ]{3,12}"
                  maxLength={12}
                  value={deliveryAddress.postal_code}
                  onChange={(event) =>
                    setDeliveryAddress((current) => ({
                      ...current,
                      postal_code: event.target.value,
                    }))
                  }
                  className="h-11 rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                />
              </label>
              <p className="self-end pb-3 text-xs text-ink-500">Country: India</p>
            </div>
          </fieldset>
          {quote && (
            <div className="border-y border-ink-100 py-4">
              <dl className="space-y-2">
                <div className="flex justify-between gap-4 text-sm">
                  <dt className="text-ink-500">Subtotal</dt>
                  <dd className="tabular-nums text-ink-800">{formatInr(quote.subtotal_cents)}</dd>
                </div>
                {quote.promotions.map((promotion, index) => (
                  <div
                    key={`${promotion.name}-${index}`}
                    className="flex justify-between gap-4 text-sm"
                  >
                    <dt className="text-ink-600">{promotion.name}</dt>
                    <dd className="tabular-nums text-leaf-700">
                      -{formatInr(promotion.discount_cents)}
                    </dd>
                  </div>
                ))}
                {quote.discount_total_cents > 0 && quote.promotions.length === 0 && (
                  <div className="flex justify-between gap-4 text-sm">
                    <dt className="text-ink-500">Discount</dt>
                    <dd className="tabular-nums text-leaf-700">
                      -{formatInr(quote.discount_total_cents)}
                    </dd>
                  </div>
                )}
                <div className="flex justify-between gap-4 border-t border-ink-100 pt-3 font-semibold">
                  <dt className="text-ink-900">Current total</dt>
                  <dd className="tabular-nums text-ink-900">{formatInr(quote.total_cents)}</dd>
                </div>
              </dl>
              <p className="mt-3 text-xs leading-relaxed text-ink-500">
                This server quote is checked again when the order is placed. No payment is
                collected.
              </p>
            </div>
          )}
        </>
      )}
      <button
        type="submit"
        disabled={!items.length || submitting}
        className="rounded-md bg-accent-700 px-5 py-3 font-semibold text-white transition-colors hover:bg-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? 'Recording order...' : 'Place demo order'}
      </button>
    </form>
  );
}
