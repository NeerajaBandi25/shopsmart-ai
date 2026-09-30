import { getCsrfToken } from '@/lib/api-client';
import { useCommerceStore } from '@/lib/commerce-store';

export interface CheckoutItem {
  product_id: string;
  quantity: number;
}

export interface OrderItem {
  product_id: string | null;
  product_name: string;
  product_sku: string;
  unit_price_cents: number;
  quantity: number;
  line_total_cents: number;
}

export interface Order {
  id: string;
  created_at: string;
  status: string;
  total_cents: number;
  items: OrderItem[];
}

async function responseError(response: Response): Promise<string> {
  if (response.status === 401) useCommerceStore.getState().clearPrivateCommerce();
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === 'string') return payload.detail;
  } catch {
    // Use the status fallback for non-JSON responses.
  }
  return `Request failed (${response.status})`;
}

export async function checkoutOrder(items: CheckoutItem[], idempotencyKey: string): Promise<Order> {
  const csrfToken = await getCsrfToken();
  const response = await fetch('/api/orders/checkout', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify({ items }),
  });
  if (!response.ok) throw new Error(await responseError(response));
  return (await response.json()) as Order;
}

export async function getOrders(): Promise<Order[]> {
  const response = await fetch('/api/orders', {
    credentials: 'include',
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(await responseError(response));
  return (await response.json()) as Order[];
}
