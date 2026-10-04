/**
 * API client for same-origin authentication and commerce operations.
 */

import { useCommerceStore } from '@/lib/commerce-store';

const AUTH_API_BASE_PATH = '/api/auth';

// Helper to handle API responses and redirect on 401
async function handleApiResponse<T>(response: Response): Promise<T> {
  const data = await response.json();

  if (!response.ok) {
    const error = data as ApiError;
    // Redirect to login on 401 Unauthorized, throw error that can be caught by components to redirect to login
    if (response.status === 401) {
      useCommerceStore.getState().clearPrivateCommerce();
      throw new Error(error.detail || 'Unauthorized - please log in');
    }
    throw new Error(error.detail || 'API request failed');
  }

  return data;
}

interface RegisterRequest {
  email: string;
  password: string;
}

interface RegisterResponse {
  user_id: string;
  email: string;
  created_at: string;
}

interface LoginRequest {
  email: string;
  password: string;
}

interface LoginResponse {
  user_id: string;
  email: string;
}

interface ApiError {
  detail: string;
  error_code: string;
  status_code: number;
}

export interface Product {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  brand: string | null;
  sku: string;
  price: number;
  list_price: number | null;
  image_url: string | null;
  image_alt: string | null;
  image_source_url?: string | null;
  image_creator?: string | null;
  image_license?: string | null;
  image_license_url?: string | null;
  image_sha256?: string | null;
  specifications: Record<string, unknown> | null;
  stock_quantity: number;
  max_purchase_quantity: number;
  delivery?: string | null;
  highlights?: string[];
  image_gallery?: { url: string; alt: string; role?: string }[];
}

export interface ProductPage {
  items: Product[];
  skip: number;
  limit: number;
  total?: number;
}

export interface HeroStoryData {
  query: string;
  budget_minor: number;
  candidates: Product[];
  recommended_product_id: string;
  recommendation: string;
  evidence: { label: string; value: string }[];
  savings_minor: number;
}

export interface HomepageData {
  categories: { value: string; label: string; count: number }[];
  featured: Product[];
  trending: Product[];
  recommendations: Product[];
  promotions: {
    name: string;
    description: string | null;
    discount_type: 'percentage' | 'fixed';
    discount_value: number;
    ends_at: string;
    scope_category: string | null;
  }[];
}

export async function getHomepage(): Promise<HomepageData> {
  const response = await fetch('/api/homepage', { credentials: 'include' });
  return handleApiResponse<HomepageData>(response);
}

export interface ProductQuery {
  q?: string;
  category?: string;
  brand?: string;
  subcategory?: string;
  min_price_minor?: number;
  max_price_minor?: number;
  in_stock_only?: boolean;
  sort?: 'newest' | 'price_asc' | 'price_desc' | 'name_asc';
}

export async function getProducts(
  skip = 0,
  limit = 24,
  filters: ProductQuery = {}
): Promise<ProductPage> {
  const query = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '' && value !== false) query.set(key, String(value));
  });
  const response = await fetch(`/api/products?${query}`, { credentials: 'include' });
  return handleApiResponse<ProductPage>(response);
}

export async function getHeroStory(): Promise<HeroStoryData | null> {
  const response = await fetch('/api/hero-shortlist', { credentials: 'include' });
  return handleApiResponse<HeroStoryData | null>(response);
}

export async function getProduct(productId: string): Promise<Product> {
  const response = await fetch(`/api/products/${encodeURIComponent(productId)}`, {
    credentials: 'include',
  });
  return handleApiResponse<Product>(response);
}

/**
 * Register a new user.
 *
 * @param email User email address
 * @param password User password
 * @returns Registration response with user_id, email, created_at
 * @throws Error if registration fails
 */
export async function register(email: string, password: string): Promise<RegisterResponse> {
  const response = await fetch(`${AUTH_API_BASE_PATH}/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password } as RegisterRequest),
    credentials: 'include',
  });

  return handleApiResponse<RegisterResponse>(response);
}

/**
 * Get current user profile (requires authentication).
 *
 * @returns User profile with user_id, email, created_at
 * @throws Error if not authenticated or request fails
 */
export async function getProfile(): Promise<RegisterResponse> {
  const response = await fetch(`${AUTH_API_BASE_PATH}/me`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
  });

  return handleApiResponse<RegisterResponse>(response);
}

/**
 * Log in a user (sets session cookie).
 *
 * @param email User email address
 * @param password User password
 * @returns Login response with user_id, email
 * @throws Error if login fails (invalid credentials, rate limited, etc.)
 */
export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${AUTH_API_BASE_PATH}/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password } as LoginRequest),
    credentials: 'include',
  });

  const result = await handleApiResponse<LoginResponse>(response);
  useCommerceStore.getState().clearPrivateCommerce();
  return result;
}

/**
 * Log out the current user (clears session cookie).
 *
 * @returns Empty promise on success
 * @throws Error if logout fails
 */
export async function logout(): Promise<void> {
  const csrfToken = await getCsrfToken();
  const response = await fetch(`${AUTH_API_BASE_PATH}/logout`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    credentials: 'include',
  });

  if (!response.ok) {
    const error = (await response.json()) as ApiError;
    if (response.status === 401) useCommerceStore.getState().clearPrivateCommerce();
    throw new Error(error.detail || 'Logout failed');
  }
  useCommerceStore.getState().clearPrivateCommerce();
}

/**
 * Get the CSRF token bound to the current session.
 *
 * Calls the authenticated GET /auth/csrf endpoint (session cookie
 * identifies the exact session row); the token is then sent as
 * X-CSRF-Token on state-changing requests such as password change.
 */
export async function getCsrfToken(): Promise<string> {
  const response = await fetch(`${AUTH_API_BASE_PATH}/csrf`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
  });

  const data = await handleApiResponse<{ csrf_token: string }>(response);
  return data.csrf_token;
}

/**
 * Change the current user's password (canonical contract).
 *
 * PUT /api/auth/password with {current_password, new_password} and
 * X-CSRF-Token header. Missing/invalid CSRF yields 403; missing/invalid
 * session yields 401.
 *
 * @param currentPassword The user's current password
 * @param newPassword The new password to set
 * @param csrfToken Optional CSRF token; fetched via GET /auth/csrf if omitted
 * @throws Error if the password change fails
 */
export async function changePassword(
  currentPassword: string,
  newPassword: string,
  csrfToken?: string
): Promise<void> {
  const token = csrfToken ?? (await getCsrfToken());
  const response = await fetch(`${AUTH_API_BASE_PATH}/password`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': token,
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
    credentials: 'include',
  });

  if (!response.ok) {
    const error = (await response.json()) as ApiError;
    if (response.status === 401) useCommerceStore.getState().clearPrivateCommerce();
    throw new Error(error.detail || 'Password change failed');
  }
  useCommerceStore.getState().clearPrivateCommerce();
}
