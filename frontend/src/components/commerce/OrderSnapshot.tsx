import type { Order } from '@/lib/order-api';
import Image from 'next/image';
import { formatInr } from '@/lib/currency';

export function formatOrderDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Date unavailable';
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function formatStatus(value: string): string {
  return value
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(' ');
}

export function OrderSnapshot({ order, title }: { order: Order; title: string }) {
  return (
    <article className="border-y border-ink-100 py-5" aria-label={title}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-bold text-ink-900">{title}</h2>
          <p className="mt-1 text-sm text-ink-600">
            <span className="font-medium">{formatStatus(order.status)}</span>
            <span aria-hidden="true"> · </span>
            <time dateTime={order.created_at}>{formatOrderDate(order.created_at)}</time>
          </p>
        </div>
      </header>

      {order.items.length > 0 ? (
        <ul className="mt-4 divide-y divide-ink-100 border-y border-ink-100">
          {order.items.map((item, index) => (
            <li
              key={`${item.product_sku}-${index}`}
              className="flex flex-wrap items-start justify-between gap-3 py-4"
            >
              <div className="flex min-w-0 items-start gap-4">
                {item.product_image_url && (
                  <div className="relative aspect-square w-16 shrink-0 overflow-hidden bg-sand-100">
                    <Image
                      src={item.product_image_url}
                      alt={item.product_image_alt || `Illustration of ${item.product_name}`}
                      fill
                      sizes="64px"
                      className="object-contain p-1"
                    />
                  </div>
                )}
                <div className="min-w-0">
                  <h3 className="break-words font-medium text-ink-900">{item.product_name}</h3>
                  <p className="mt-1 text-xs text-ink-500">SKU {item.product_sku}</p>
                  <p className="mt-1 text-sm text-ink-600">
                    {item.quantity} × {formatInr(item.unit_price_cents)}
                  </p>
                </div>
              </div>
              <p className="font-semibold tabular-nums text-ink-900">
                {formatInr(item.line_total_cents)}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-ink-500">Item details are unavailable for this order.</p>
      )}

      {order.delivery_address && (
        <section className="mt-4 border-t border-ink-100 pt-4" aria-label="Delivery address">
          <h3 className="text-xs font-semibold uppercase tracking-caps text-ink-500">
            Delivery address
          </h3>
          <address className="mt-2 not-italic text-sm leading-relaxed text-ink-700">
            {order.delivery_address.recipient_name}
            <br />
            {order.delivery_address.address_line1}
            {order.delivery_address.address_line2 && (
              <>
                <br />
                {order.delivery_address.address_line2}
              </>
            )}
            <br />
            {order.delivery_address.city}, {order.delivery_address.region}{' '}
            {order.delivery_address.postal_code}
            <br />
            {order.delivery_address.phone}
          </address>
        </section>
      )}

      <dl className="mt-4 space-y-2">
        <div className="flex justify-between gap-4 text-sm">
          <dt className="text-ink-500">Subtotal</dt>
          <dd className="tabular-nums text-ink-800">{formatInr(order.subtotal_cents)}</dd>
        </div>
        {order.promotion_snapshot.map((promotion, index) => {
          const name = typeof promotion.name === 'string' ? promotion.name : 'Promotion';
          const discount =
            typeof promotion.discount_cents === 'number' ? promotion.discount_cents : null;
          return (
            <div key={`${name}-${index}`} className="flex justify-between gap-4 text-sm">
              <dt className="text-ink-600">{name}</dt>
              {discount !== null && (
                <dd className="tabular-nums text-leaf-700">-{formatInr(discount)}</dd>
              )}
            </div>
          );
        })}
        {order.discount_total_cents > 0 && order.promotion_snapshot.length === 0 && (
          <div className="flex justify-between gap-4 border-t border-ink-100 pt-3 text-sm">
            <dt className="font-medium text-ink-700">Discount</dt>
            <dd className="font-medium tabular-nums text-leaf-700">
              -{formatInr(order.discount_total_cents)}
            </dd>
          </div>
        )}
        <div className="flex justify-between gap-4 border-t border-ink-100 pt-3">
          <dt className="font-semibold text-ink-900">Order total</dt>
          <dd className="font-display text-xl font-bold tabular-nums text-ink-900">
            {formatInr(order.total_cents)}
          </dd>
        </div>
      </dl>
    </article>
  );
}
