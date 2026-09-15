/**
 * API client for authentication and user operations.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

interface RegisterRequest {
  email: string;
  password: string;
}

interface RegisterResponse {
  user_id: string;
  email: string;
  created_at: string;
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

  const data = await response.json();

  if (!response.ok) {
    const error = data as ApiError;
    throw new Error(error.detail || 'Registration failed');
  }

  return data as RegisterResponse;
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

  const data = await response.json();

  if (!response.ok) {
    const error = data as ApiError;
    throw new Error(error.detail || 'Failed to fetch profile');
  }

  return data as RegisterResponse;
}
