'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/Button';

export function PromoBanner() {
  return (
    <div className="relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-r from-primary-50 via-primary-100 to-primary-50/50"></div>
      <div className="relative py-16 sm:py-20 lg:py-24 text-center">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="mb-6 text-3xl sm:text-4xl font-bold text-gray-900">
            ShopSmart AI: Your Secure Shopping Assistant
          </h1>
          <p className="mb-8 max-w-2xl mx-auto text-lg text-gray-600">
            Experience safe, private account management with our AI-powered platform.
            Register and login securely to access your personalized dashboard.
          </p>
          <div className="flex flex-col sm:flex-row sm:space-x-4 space-y-4 sm:space-y-0 justify-center">
            <Link href="/auth/register" className="flex-1">
              <Button variant="primary" size="md" className="w-full">
                Get Started
              </Button>
            </Link>
            <Link href="/dashboard" className="ml-4 sm:ml-0 flex-1">
              <Button variant="secondary" size="md" className="w-full">
                Learn More
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}