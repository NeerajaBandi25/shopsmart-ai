'use client';

import Image from 'next/image';
import { useRef, useState } from 'react';
import { checkoutOrder, type CheckoutItem, type DeliveryAddress } from '@/lib/order-api';
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
  onRedirect?: (url: string) => void;
}

function createIdempotencyKey(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

const CHECKOUT_KEY_STORAGE = 'shopsmart.checkout.idempotency.v1';

function getCheckoutIdempotencyKey(items: CheckoutLine[], couponCode?: string | null): string {
  const fingerprint = JSON.stringify({
    items: items
      .map(({ product_id, quantity }) => ({ product_id, quantity }))
      .sort((left, right) => left.product_id.localeCompare(right.product_id)),
    couponCode: couponCode || null,
  });
  try {
    const saved = sessionStorage.getItem(CHECKOUT_KEY_STORAGE);
    if (saved) {
      const parsed = JSON.parse(saved) as { fingerprint?: unknown; key?: unknown };
      if (parsed.fingerprint === fingerprint && typeof parsed.key === 'string') return parsed.key;
    }
    const key = createIdempotencyKey();
    sessionStorage.setItem(CHECKOUT_KEY_STORAGE, JSON.stringify({ fingerprint, key }));
    return key;
  } catch {
    return createIdempotencyKey();
  }
}

export function CheckoutForm({ items, couponCode, quote, onRedirect }: CheckoutFormProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
    idempotencyKey.current ??= getCheckoutIdempotencyKey(items, couponCode);
    try {
      const order = await checkoutOrder(
        items.map(({ product_id, quantity }) => ({ product_id, quantity })),
        idempotencyKey.current,
        couponCode,
        { ...deliveryAddress, address_line2: deliveryAddress.address_line2 || null }
      );
      if (!order.checkout_url) {
        throw new Error('Secure payment checkout is unavailable. Your order was not completed.');
      }
      const checkoutUrl = new URL(order.checkout_url);
      if (checkoutUrl.protocol !== 'https:' || checkoutUrl.hostname !== 'checkout.stripe.com') {
        throw new Error('The secure payment destination could not be verified.');
      }
      (onRedirect || ((url: string) => window.location.assign(url)))(checkoutUrl.toString());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Checkout could not be completed.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-6">
      <p className="border-l-2 border-accent-500 bg-sand-50 px-4 py-3 text-sm leading-relaxed text-ink-700">
        You will continue to Stripe-hosted test checkout. ShopSmart never receives your card
        details; no live payment is processed.
      </p>
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
                The server rechecks current prices, stock and promotions before creating a payment
                session.
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
        {submitting ? 'Preparing secure checkout...' : 'Continue to secure checkout'}
      </button>
    </form>
  );
}
