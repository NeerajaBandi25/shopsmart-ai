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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

async function parseCartResponse(response: Response): Promise<Cart> {
  const data = (await response.json()) as Cart | { detail?: string };
  if (!response.ok) {
    const detail = 'detail' in data ? data.detail : undefined;
    throw new Error(detail || 'Cart request failed.');
  }
  return data as Cart;
}

function getCartUrl(path: string): string {
  if (!API_BASE_URL) {
    throw new Error('The cart is unavailable right now.');
  }
  return `${API_BASE_URL}${path}`;
}

export async function getCart(): Promise<Cart> {
  const response = await fetch(getCartUrl('/cart'), {
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
  const response = await fetch(getCartUrl(path), {
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
  return mutateCart('/cart/items', 'POST', { product_id: productId, quantity });
}

export function setCartItemQuantity(productId: string, quantity: number): Promise<Cart> {
  return mutateCart(`/cart/items/${productId}`, 'PUT', { quantity });
}

export function removeCartItem(productId: string): Promise<Cart> {
  return mutateCart(`/cart/items/${productId}`, 'DELETE');
}
