'use client';

import { RegistrationForm } from '@/components/registration-form';
import Link from 'next/link';

/**
 * Register page — premium ShopSmart authentication.
 * Same form-first centered composition as login: compact brand/eyebrow/
 * heading, clean card, subtle background layer that never competes with the
 * form. Fields and behavior come from RegistrationForm unchanged.
 */
export default function RegisterPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-blush-50">
      {/* Decorative editorial layer: soft glows + fine grid, low-key */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div
          className="absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              'linear-gradient(rgba(109, 31, 66, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(109, 31, 66, 0.05) 1px, transparent 1px)',
            backgroundSize: '28px 28px',
          }}
        />
        <div className="absolute -top-24 -right-20 h-72 w-72 rounded-full bg-accent-200/40 blur-3xl" />
        <div className="absolute -bottom-28 -left-24 h-80 w-80 rounded-full bg-sand-200/50 blur-3xl" />
        {/* Small monogram accent, corner-placed and out of the way */}
        <span className="absolute right-6 top-6 hidden font-display text-4xl font-bold text-accent-700/15 select-none lg:block">
          S
        </span>
      </div>

      {/* Content */}
      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-4 py-10 sm:py-12">
        {/* Brand */}
        <Link
          href="/"
          className="inline-flex items-baseline gap-2.5 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
        >
          <span className="font-display text-lg font-bold tracking-display text-ink-900">
            ShopSmart AI
          </span>
          <span aria-hidden="true" className="h-1 w-1 rounded-full bg-accent-500" />
          <span className="text-[11px] font-semibold uppercase tracking-caps text-ink-500">
            The Premium Edit
          </span>
        </Link>

        {/* Heading block — compact, form remains the priority */}
        <div className="mt-8 space-y-2 text-center">
          <p className="text-xs font-semibold uppercase tracking-caps text-accent-600">
            Membership
          </p>
          <h1 className="font-display text-3xl font-bold tracking-display text-ink-900 sm:text-4xl">
            Create your account
          </h1>
          <p className="text-sm text-ink-500">
            Premium shopping, secured from your first sign-in.
          </p>
        </div>

        {/* Form card */}
        <div className="mt-8 w-full max-w-md rounded-tile bg-white p-6 shadow-tile sm:p-8">
          <RegistrationForm />
        </div>
      </div>
    </div>
  );
}
