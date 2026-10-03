import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { getSetCookieHeaders } from './app/api/auth/_proxy';

// Define paths that require authentication
const protectedPaths = [
  '/dashboard',
  '/orders',
  '/account',
  '/assistant',
  // Add other protected paths as needed
];

// Define paths that are public (no auth required)
const publicPaths = [
  '/auth/login',
  '/auth/register',
  '/api/auth/login',
  '/api/auth/register',
  '/api/auth/me', // Middleware's same-origin session check
  '/_next',
  '/favicon.ico',
];

function safeRedirectTo(pathname: string): string {
  if (!pathname.startsWith('/') || pathname.startsWith('//') || pathname.includes('\\')) {
    return '/dashboard';
  }
  return pathname;
}

function copySessionCookies(source: Headers, target: Headers): void {
  for (const cookie of getSetCookieHeaders(source)) {
    target.append('Set-Cookie', cookie);
  }
}

async function forwardSessionFailure(response: Response): Promise<Response> {
  const headers = new Headers({ 'Cache-Control': 'no-store' });
  const contentType = response.headers.get('content-type');
  if (contentType) headers.set('Content-Type', contentType);
  copySessionCookies(response.headers, headers);

  const status = response.status >= 400 ? response.status : 503;
  const body = [204, 205, 304].includes(status) ? null : await response.text();
  return new Response(body, { status, headers });
}

function serviceUnavailable(): Response {
  return new Response(
    JSON.stringify({
      detail: 'Authentication service unavailable',
      error_code: 'auth_service_unavailable',
      status_code: 503,
    }),
    {
      status: 503,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
    }
  );
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Check if path is public
  const isPublicPath = publicPaths.some((path) => pathname.startsWith(path));

  if (isPublicPath) {
    return NextResponse.next();
  }

  // Check if path is protected
  const isProtectedPath = protectedPaths.some((path) => pathname.startsWith(path));

  if (!isProtectedPath) {
    // For paths not explicitly protected or public, we'll still check auth
    // but we won't redirect to login automatically (they might be public)
    return NextResponse.next();
  }

  // For protected paths, check session validity
  try {
    const headers = new Headers({ Accept: 'application/json' });
    const cookie = request.headers.get('cookie');
    if (cookie) headers.set('Cookie', cookie);

    const sessionResponse = await fetch(new URL('/api/auth/me', request.url), {
      method: 'GET',
      headers,
      cache: 'no-store',
      redirect: 'manual',
    });

    if (sessionResponse.status === 200) {
      const response = NextResponse.next();
      copySessionCookies(sessionResponse.headers, response.headers);
      return response;
    }

    if (sessionResponse.status === 401) {
      const url = new URL('/auth/login', request.url);
      url.searchParams.set('redirectTo', safeRedirectTo(pathname));
      const response = NextResponse.redirect(url);
      copySessionCookies(sessionResponse.headers, response.headers);
      return response;
    }

    return forwardSessionFailure(sessionResponse);
  } catch {
    return serviceUnavailable();
  }
}

// Configure middleware to run on specific paths
export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico
     * - public folder
     */
    '/((?!_next/static|_next/image|favicon.ico|public).*)',
  ],
};
