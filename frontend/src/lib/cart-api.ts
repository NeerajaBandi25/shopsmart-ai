'use client';

import { getCsrfToken } from '@/lib/api-client';

export interface CartItem {
  product_id: string;
  name: string;
  sku: string;
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
}

const CART_API_BASE_PATH = '/api/cart';

async function parseCartResponse(response: Response): Promise<Cart> {
  const data = (await response.json()) as Cart | { detail?: string };
  if (!response.ok) {
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
  body?: { product_id?: string; quantity?: number }
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
