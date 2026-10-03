'use client';

import { useEffect, useState } from 'react';
import { getOrders, type Order } from '@/lib/order-api';
import { OrderSnapshot, formatOrderDate } from '@/components/commerce/OrderSnapshot';

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
        <li key={order.id} className="py-6 first:pt-0">
          <OrderSnapshot order={order} title={`Order from ${formatOrderDate(order.created_at)}`} />
        </li>
      ))}
    </ol>
  );
}
