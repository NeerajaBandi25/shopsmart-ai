import { getCsrfToken } from '@/lib/api-client';
import { useCommerceStore } from '@/lib/commerce-store';

export interface CheckoutItem {
  product_id: string;
  quantity: number;
}

export interface DeliveryAddress {
  recipient_name: string;
  phone: string;
  address_line1: string;
  address_line2?: string | null;
  city: string;
  region: string;
  postal_code: string;
  country_code: 'IN';
}

export interface OrderItem {
  product_id: string | null;
  product_name: string;
  product_sku: string;
  product_image_url?: string | null;
  product_image_alt?: string | null;
  unit_price_cents: number;
  quantity: number;
  line_total_cents: number;
}

export interface Order {
  id: string;
  created_at: string;
  status: string;
  payment_status?:
    'pending' | 'requires_action' | 'succeeded' | 'failed' | 'cancelled' | 'refunded' | null;
  payment_method_label?: string | null;
  checkout_url?: string | null;
  subtotal_cents: number;
  discount_total_cents: number;
  total_cents: number;
  delivery_address?: DeliveryAddress | null;
  promotion_snapshot: {
    promotion_id: string;
    code: string | null;
    name: string;
    promotion_type: string;
    value: number;
    discount_cents: number;
    applied_scope: Record<string, string>;
    evaluated_at: string;
  }[];
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

export async function checkoutOrder(
  items: CheckoutItem[],
  idempotencyKey: string,
  couponCode: string | null | undefined,
  deliveryAddress: DeliveryAddress
): Promise<Order> {
  const csrfToken = await getCsrfToken();
  const response = await fetch('/api/orders/checkout', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify({
      items,
      ...(couponCode ? { coupon_code: couponCode } : {}),
      delivery_address: deliveryAddress,
    }),
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

export async function getOrder(orderId: string): Promise<Order> {
  const response = await fetch(`/api/orders/${encodeURIComponent(orderId)}`, {
    credentials: 'include',
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(await responseError(response));
  return (await response.json()) as Order;
}

export async function retryPayment(orderId: string): Promise<Order> {
  const csrfToken = await getCsrfToken();
  const response = await fetch(`/api/orders/${encodeURIComponent(orderId)}/payment/retry`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRF-Token': csrfToken },
  });
  if (!response.ok) throw new Error(await responseError(response));
  return (await response.json()) as Order;
}
