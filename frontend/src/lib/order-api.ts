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

const apiBase = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '');

function apiUrl(path: string): string {
  if (!apiBase) throw new Error('Order services are unavailable right now.');
  return `${apiBase}${path}`;
}

async function getCsrfToken(): Promise<string> {
  const response = await fetch(apiUrl('/auth/csrf'), {
    credentials: 'include',
    cache: 'no-store',
  });
  if (!response.ok) {
    throw new Error(await responseError(response));
  }
  const payload = (await response.json()) as { csrf_token: string };
  return payload.csrf_token;
}

async function responseError(response: Response): Promise<string> {
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
  const response = await fetch(apiUrl('/orders/checkout'), {
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
  const response = await fetch(apiUrl('/orders'), {
    credentials: 'include',
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(await responseError(response));
  return (await response.json()) as Order[];
}
