'use client';

import { useEffect, useState } from 'react';
import { getProfile } from '@/lib/api-client';
import { LogoutButton } from './logout-button';
import Link from 'next/link';

export default function Nav() {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
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
  }, []);

  if (isLoading) {
    return (
      <nav className="bg-white border-b border-gray-200 px-4 sm:px-6">
        <div className="max-w-7xl mx-auto flex h-16 items-center justify-between">
          <div className="flex items-center">
            <span className="text-xl font-semibold text-gray-800">ShopSmart AI</span>
          </div>
          <div className="hidden md:flex md:items-center md:space-x-4">
            {/* Loading state - show spinner on the right */}
            <div className="flex items-center">
              <div className="animate-spin h-5 w-5 border-b-2 border-blue-600"></div>
            </div>
          </div>
        </div>
      </nav>
    );
  }

  return (
    <nav className="bg-white border-b border-gray-200 px-4 sm:px-6">
      <div className="max-w-7xl mx-auto flex h-16 items-center justify-between">
        <div className="flex items-center">
          <span className="text-xl font-semibold text-gray-800">ShopSmart AI</span>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:space-x-4 space-y-2 sm:space-y-0">
          {isAuthenticated ? (
            <>
              <Link
                href="/dashboard"
                className="text-sm font-medium text-gray-600 hover:text-gray-900"
              >
                Dashboard
              </Link>
              <Link
                href="/account"
                className="ml-4 text-sm font-medium text-gray-600 hover:text-gray-900"
              >
                Account
              </Link>
              <LogoutButton className="ml-4" />
            </>
          ) : (
            <>
              {/* Unauthenticated state - no auth links */}
            </>
          )}
        </div>
      </div>
    </nav>
  );
}