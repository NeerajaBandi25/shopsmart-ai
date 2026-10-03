'use client';

import { getCsrfToken } from '@/lib/api-client';
import { useCommerceStore } from '@/lib/commerce-store';

export interface CartItem {
  product_id: string;
  name: string;
  sku: string;
  image_url?: string | null;
  image_alt?: string | null;
  unit_price: number;
  quantity: number;
  line_total: number;
  stock_quantity: number;
  max_purchase_quantity: number;
}

export interface Cart {
  items: CartItem[];
  subtotal: number;
  currency: string;
  coupon_code: string | null;
  coupon_evaluation: {
    promotion_id: string | null;
    code: string | null;
    name: string | null;
    eligible: boolean;
    reason_code: string;
    discount_cents: number;
    applied_scope: Record<string, string>;
  } | null;
  applied_promotions: {
    promotion_id: string;
    code: string | null;
    name: string;
    promotion_type: string;
    value: number;
    discount_cents: number;
    applied_scope: Record<string, string>;
  }[];
  discount_total_cents: number;
  total_cents: number;
}

const CART_API_BASE_PATH = '/api/cart';

async function parseCartResponse(response: Response): Promise<Cart> {
  const data = (await response.json()) as Cart | { detail?: string };
  if (!response.ok) {
    if (response.status === 401) useCommerceStore.getState().clearPrivateCommerce();
    const detail = 'detail' in data ? data.detail : undefined;
    throw new Error(detail || 'Cart request failed.');
  }
  return data as Cart;
}

export async function getCart(): Promise<Cart> {
  const response = await fetch(CART_API_BASE_PATH, {
    method: 'GET',
    credentials: 'include',
  });
  return parseCartResponse(response);
}

async function mutateCart(
  path: string,
  method: 'POST' | 'PUT' | 'DELETE',
  body?: { product_id?: string; quantity?: number; code?: string }
): Promise<Cart> {
  const csrfToken = await getCsrfToken();
  const response = await fetch(`${CART_API_BASE_PATH}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    credentials: 'include',
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  return parseCartResponse(response);
}

export function addCartItem(productId: string, quantity: number): Promise<Cart> {
  return mutateCart('/items', 'POST', { product_id: productId, quantity });
}

export function setCartItemQuantity(productId: string, quantity: number): Promise<Cart> {
  return mutateCart(`/items/${productId}`, 'PUT', { quantity });
}

export function removeCartItem(productId: string): Promise<Cart> {
  return mutateCart(`/items/${productId}`, 'DELETE');
}

export function applyCartCoupon(code: string): Promise<Cart> {
  return mutateCart('/coupon', 'POST', { code });
}

export function removeCartCoupon(): Promise<Cart> {
  return mutateCart('/coupon', 'DELETE');
}
