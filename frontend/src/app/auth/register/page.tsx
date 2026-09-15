'use client';

import { RegistrationForm } from '@/components/registration-form';

export default function RegisterPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div>
          <h1 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Create Account
          </h1>
          <p className="mt-2 text-center text-sm text-gray-600">
            Join ShopSmart AI to get started
          </p>
        </div>

        <RegistrationForm />
      </div>
    </div>
  );
}
