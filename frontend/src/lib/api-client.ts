/**
 * API client for authentication and user operations.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

// Helper to handle API responses and redirect on 401
async function handleApiResponse<T>(response: Response): Promise<T> {
  const data = await response.json();

  if (!response.ok) {
    const error = data as ApiError;
    // Redirect to login on 401 Unauthorized, throw error that can be caught by components to redirect to login
    if (response.status === 401) {
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

/**
 * Register a new user.
 *
 * @param email User email address
 * @param password User password
 * @returns Registration response with user_id, email, created_at
 * @throws Error if registration fails
 */
export async function register(
  email: string,
  password: string
): Promise<RegisterResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
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
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
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
export async function login(
  email: string,
  password: string
): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password } as LoginRequest),
    credentials: 'include',
  });

  return handleApiResponse<LoginResponse>(response);
}

/**
 * Log out the current user (clears session cookie).
 *
 * @returns Empty promise on success
 * @throws Error if logout fails
 */
export async function logout(): Promise<void> {
  const csrfToken = await getCsrfToken();
  const response = await fetch(`${API_BASE_URL}/auth/logout`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json() as ApiError;
    throw new Error(error.detail || 'Logout failed');
  }
}

/**
 * Get the CSRF token bound to the current session.
 *
 * Calls the authenticated GET /auth/csrf endpoint (session cookie
 * identifies the exact session row); the token is then sent as
 * X-CSRF-Token on state-changing requests such as password change.
 */
export async function getCsrfToken(): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/csrf`, {
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
 * PUT /api/v1/users/password with {current_password, new_password} and
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
  const response = await fetch(`${API_BASE_URL}/users/password`, {
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
    const error = await response.json() as ApiError;
    throw new Error(error.detail || 'Password change failed');
  }
}