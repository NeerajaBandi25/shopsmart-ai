'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/Button';

export function HeroCampaign() {
  return (
    <section className="py-16 sm:py-20 lg:py-24 bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid gap-8 sm:grid-cols-2 items-center">
          <div className="space-y-6 text-center sm:text-left">
            <h2 className="mb-4 text-3xl sm:text-4xl font-bold text-gray-900">
              Secure Account Management, Powered by AI
            </h2>
            <p className="mb-6 max-w-xl mx-auto sm:mx-0 text-lg text-gray-600">
              ShopSmart AI provides a safe, private environment for managing your
              online identity. Our AI-enhanced security protects your account while
              you focus on what matters most.
            </p>
            <Link href="/auth/register" className="inline-flex items-center">
              <Button variant="primary" size="md">
                Sign Up Now
              </Button>
            </Link>
          </div>
          <div className="relative h-64 sm:h-96">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-50 via-indigo-50 to-purple-50 rounded-xl shadow-lg overflow-hidden">
              <div className="absolute inset-0 flex items-center justify-center text-gray-400 text-5xl" aria-hidden="true">
                🔐✨
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}