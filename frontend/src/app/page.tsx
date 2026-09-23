'use client';

import Nav from '@/components/nav';
import Link from 'next/link';
import { Button } from '@/components/ui/Button';

export default function HomePage() {
  return (
    <>
      <Nav />
      <main className="min-h-screen flex flex-col bg-gray-50">
        <div className="flex-1 py-8 px-4 sm:px-6 lg:px-8">
          {/* Hero Section */}
          <div className="text-center space-y-6">
            <h1 className="text-4xl font-bold text-gray-900 sm:text-5xl">
              ShopSmart AI
            </h1>
            <p className="max-w-xl mx-auto text-lg text-gray-600">
              AI-powered shopping assistant for secure account management.
            </p>
            <div className="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-3">
              <Link
                href="/auth/register"
                className="flex-1"
              >
                <Button variant="primary" size="md" className="w-full">
                  Sign Up
                </Button>
              </Link>
              <Link
                href="/auth/login"
                className="ml-4 sm:ml-0 flex-1"
              >
                <Button variant="secondary" size="md" className="w-full">
                  Log In
                </Button>
              </Link>
            </div>
          </div>

          {/* Features Section */}
          <div className="space-y-8 text-center">
            <h2 className="text-2xl font-semibold text-gray-900">
              Secure Account Management
            </h2>
            <div className="max-w-xl mx-auto grid gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="flex flex-col items-center space-y-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-50">
                  <span className="text-blue-600 text-2xl">🔐</span>
                </div>
                <h3 className="font-medium text-gray-800">Registration & Login</h3>
                <p className="text-sm text-gray-600">
                  Create an account and sign in securely with email and password.
                </p>
              </div>
              <div className="flex flex-col items-center space-y-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-50">
                  <span className="text-blue-600 text-2xl">👤</span>
                </div>
                <h3 className="font-medium text-gray-800">Profile Management</h3>
                <p className="text-sm text-gray-600">
                  View your account information and update your password.
                </p>
              </div>
              <div className="flex flex-col items-center space-y-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-50">
                  <span className="text-blue-600 text-2xl">🔒</span>
                </div>
                <h3 className="font-medium text-gray-800">Security Features</h3>
                <p className="text-sm text-gray-600">
                  Password change requires current password and logs out all sessions.
                </p>
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}