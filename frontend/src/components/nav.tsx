'use client';

import { useEffect, useState } from 'react';
import { getProfile } from '@/lib/api-client';
import { LogoutButton } from './logout-button';
import Link from 'next/link';
import { useCommerceStore } from '@/lib/commerce-store';

interface NavProps {
  /**
   * Whether to probe /auth/me on mount to discover session state.
   *
   * The session cookie is HttpOnly, so client JS cannot know whether it
   * exists. Server components CAN check cookie presence: pages that provably
   * have no session cookie (e.g. the public homepage for signed-out visitors)
   * pass probeAuth={false} so Nav skips a request that would be guaranteed
   * to return 401. Authenticated layouts keep the default probe.
   */
  probeAuth?: boolean;
}

export default function Nav({ probeAuth = true }: NavProps) {
  const cartItemCount = useCommerceStore((state) => state.cartItemCount);
  const [isLoading, setIsLoading] = useState(probeAuth);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (!probeAuth) {
      // Server-side cookie check proved there is no session cookie:
      // probing /auth/me could only ever 401, so render signed-out
      // immediately and make no network request.
      setIsLoading(false);
      return;
    }

    const checkAuth = async () => {
      try {
        await getProfile();
        setIsAuthenticated(true);
      } catch {
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, [probeAuth]);

  // Editorial polish: sticky bar with slim accent strip. The white/border base
  // classes are asserted by nav.test.tsx and must not be removed.
  const navClasses = 'bg-white border-b border-gray-200 sticky top-0 z-50';

  // Refined link treatment: color shift + growing accent underline (CSS only),
  // with a visible keyboard-focus ring.
  const navLinkClasses =
    'relative rounded-sm px-0.5 text-sm font-medium text-ink-500 transition-colors duration-200 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 after:absolute after:left-0 after:-bottom-1 after:h-px after:w-0 after:bg-accent-500 after:transition-all after:duration-300 hover:after:w-full';

  const wordmark = (
    <Link
      href="/"
      className="inline-flex items-baseline gap-3 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
    >
      <span className="font-display text-xl font-bold tracking-display text-ink-900">
        ShopSmart AI
      </span>
      <span
        aria-hidden="true"
        className="hidden h-1 w-1 rounded-full bg-accent-500 sm:inline-block"
      />
      <span className="hidden text-[11px] font-semibold uppercase tracking-caps text-ink-500 sm:inline">
        The Premium Edit
      </span>
    </Link>
  );

  // Calm static announcement line — concise messaging, no ticker repetition.
  const announcementStrip = (
    <div className="bg-accent-800 text-white">
      <p className="mx-auto max-w-7xl px-4 py-1.5 text-center text-[10px] font-semibold uppercase tracking-caps sm:text-[11px]">
        New Season
        <span aria-hidden="true" className="mx-2 text-white/50">
          ·
        </span>
        The AI Edit
        <span aria-hidden="true" className="mx-2 text-white/50">
          ·
        </span>
        Members First
      </p>
    </div>
  );

  // Signed-out CTA pair (existing public routes only). Reused in both the
  // loading and settled branches so the header is complete in either state.
  const signedOutCtas = (
    <div className="flex flex-col items-stretch gap-3 md:flex-row md:items-center md:gap-5">
      <Link
        href="/auth/login"
        className="rounded-sm text-sm font-medium text-ink-500 transition-colors duration-200 hover:text-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
        onClick={() => setIsMobileMenuOpen(false)}
      >
        Sign In
      </Link>
      <Link
        href="/auth/register"
        className="rounded-full bg-accent-600 px-4 py-1.5 text-sm font-semibold text-white shadow-tile transition-colors duration-200 hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
        onClick={() => setIsMobileMenuOpen(false)}
      >
        Create Account
      </Link>
    </div>
  );

  if (isLoading) {
    return (
      <nav className={navClasses}>
        {announcementStrip}
        <div
          aria-hidden="true"
          className="h-0.5 w-full bg-gradient-to-r from-accent-600 via-accent-300 to-accent-600"
        />
        <div className="max-w-7xl mx-auto flex min-h-[3.75rem] items-center justify-between gap-4 sm:min-h-[4rem] px-4 sm:px-6 lg:px-8">
          <div className="flex items-center">{wordmark}</div>
          <div className="hidden md:flex md:items-center md:space-x-4">
            {/* Loading state - show spinner on the right */}
            <div className="flex items-center">
              <div className="animate-spin h-5 w-5 border-b-2 border-accent-600"></div>
            </div>
          </div>
        </div>
      </nav>
    );
  }

  return (
    <nav className={navClasses}>
      {announcementStrip}
      <div
        aria-hidden="true"
        className="h-0.5 w-full bg-gradient-to-r from-accent-600 via-accent-300 to-accent-600"
      />
      <div className="relative max-w-7xl mx-auto flex min-h-[3.75rem] items-center justify-between gap-4 sm:min-h-[4rem] px-4 sm:px-6 lg:px-8">
        <div className="flex items-center">{wordmark}</div>
        <div className="flex items-center">
          <button
            type="button"
            aria-label="Open shopping commands"
            onClick={() => window.dispatchEvent(new Event('shopsmart-commands'))}
            className="min-h-11 rounded-sm px-3 text-sm font-semibold text-ink-900 focus-visible:ring-2 focus-visible:ring-accent-500 sm:hidden"
          >
            Search
          </button>
          <button
            type="button"
            aria-label={isMobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
            aria-expanded={isMobileMenuOpen}
            aria-controls="primary-navigation"
            onClick={() => setIsMobileMenuOpen((open) => !open)}
            className="rounded-sm px-2 py-1.5 text-sm font-semibold text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 md:hidden"
          >
            {isMobileMenuOpen ? 'Close' : 'Menu'}
          </button>
          <div
            id="primary-navigation"
            className={`${isMobileMenuOpen ? 'flex' : 'hidden'} absolute left-0 right-0 top-full z-50 flex-col items-stretch gap-3 border-b border-gray-200 bg-white px-4 py-4 shadow-tile md:static md:z-auto md:flex md:flex-row md:items-center md:gap-5 md:border-0 md:bg-transparent md:px-0 md:py-0 md:shadow-none`}
          >
            {isAuthenticated ? (
              <>
                <Link
                  href="/dashboard"
                  className={navLinkClasses}
                  onClick={() => setIsMobileMenuOpen(false)}
                >
                  Dashboard
                </Link>
                <Link
                  href="/cart"
                  className={navLinkClasses}
                  aria-label={`Cart, ${cartItemCount} ${cartItemCount === 1 ? 'item' : 'items'}`}
                  onClick={() => setIsMobileMenuOpen(false)}
                >
                  Cart <span aria-hidden="true">({cartItemCount})</span>
                </Link>
                <Link
                  href="/orders"
                  className={navLinkClasses}
                  onClick={() => setIsMobileMenuOpen(false)}
                >
                  Orders
                </Link>
                <Link
                  href="/account"
                  className={navLinkClasses}
                  onClick={() => setIsMobileMenuOpen(false)}
                >
                  Account
                </Link>
                <LogoutButton className="sm:ml-1 sm:w-auto" />
              </>
            ) : (
              signedOutCtas
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
