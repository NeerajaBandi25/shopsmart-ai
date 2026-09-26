'use client';

import { useEffect, useState } from 'react';
import { getOrders, type Order } from '@/lib/order-api';

function formatCents(cents: number): string {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' }).format(
    cents / 100
  );
}

export function OrderHistory() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getOrders()
      .then((result) => {
        if (active) {
          setOrders(result);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : 'Order history is unavailable.');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [refreshKey]);

  if (loading)
    return (
      <p role="status" className="text-sm text-ink-500">
        Loading orders...
      </p>
    );
  if (error) {
    return (
      <div className="space-y-3" role="alert">
        <p className="text-sm text-red-700">{error}</p>
        <button
          type="button"
          onClick={() => setRefreshKey((current) => current + 1)}
          className="font-medium text-accent-700 underline underline-offset-4"
        >
          Try again
        </button>
      </div>
    );
  }
  if (!orders.length) {
    return (
      <p role="status" className="text-sm text-ink-500">
        No orders yet.
      </p>
    );
  }

  return (
    <ol className="divide-y divide-ink-100">
      {orders.map((order) => (
        <li key={order.id} className="space-y-4 py-6 first:pt-0">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold text-ink-900">Order #{order.id}</h2>
              <p className="mt-1 text-sm text-ink-500">
                {new Date(order.created_at).toLocaleString()} · {order.status}
              </p>
            </div>
            <p className="font-semibold tabular-nums text-ink-900">
              {formatCents(order.total_cents)}
            </p>
          </div>
          <ul className="space-y-2 border-l-2 border-accent-200 pl-4">
            {order.items.map((item) => (
              <li
                key={`${order.id}-${item.product_sku}`}
                className="flex flex-wrap justify-between gap-2 text-sm"
              >
                <span className="text-ink-700">
                  {item.product_name} <span className="text-ink-500">× {item.quantity}</span>
                </span>
                <span className="tabular-nums text-ink-700">
                  {formatCents(item.line_total_cents)}
                </span>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}
