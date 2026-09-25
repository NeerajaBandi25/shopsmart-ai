'use client';

import { useEffect, useState } from 'react';
import { getProfile, logout } from '@/lib/api-client';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Alert } from '@/components/ui/Alert';
import AuthenticatedLayout from '@/app/authenticated-layout';

/**
 * Member dashboard — the authenticated continuation of the homepage design
 * language. Displays only data that exists (user_id, email, created_at) and
 * only actions that already exist (account settings, sign out). No commerce,
 * analytics, or AI features are presented here.
 */
export default function DashboardPage() {
  const [profile, setProfile] = useState<null | {
    user_id: string;
    email: string;
    created_at: string;
  }>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [signingOut, setSigningOut] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const loadProfile = async () => {
      try {
        setLoading(true);
        const data = await getProfile();
        setProfile(data);
        setError(null);
      } catch (err) {
        // Redirect to login if not authenticated
        setError(err instanceof Error ? err.message : 'Failed to load profile');
        router.push('/auth/login');
      } finally {
        setLoading(false);
      }
    };

    loadProfile();
  }, [router]);

  const handleSignOut = async () => {
    setSigningOut(true);
    try {
      await logout();
      router.push('/auth/login');
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setSigningOut(false);
    }
  };

  if (loading) {
    // Show loading state within the authenticated layout
    return (
      <AuthenticatedLayout>
        <div className="flex flex-col items-center justify-center py-24">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent-600"></div>
        </div>
      </AuthenticatedLayout>
    );
  }

  if (error) {
    return (
      <AuthenticatedLayout>
        <div className="max-w-3xl mx-auto flex flex-col items-center justify-center py-24">
          <Alert variant="error" message={error} />
        </div>
      </AuthenticatedLayout>
    );
  }

  if (!profile) {
    // This state should not happen, but fallback to login
    router.push('/auth/login');
    return null;
  }

  const memberName = profile.email.split('@')[0];
  const memberSince = new Date(profile.created_at).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  return (
    <AuthenticatedLayout>
      <div className="max-w-5xl mx-auto space-y-8 sm:space-y-10">
        {/* Welcome / identity area */}
        <div className="space-y-2.5">
          <p className="text-xs font-semibold uppercase tracking-caps text-accent-600">
            Member Studio
          </p>
          <h1 className="font-display text-display-md sm:text-display-lg font-bold tracking-display text-ink-900 text-balance">
            Welcome back, <span className="text-accent-600">{memberName}</span>
          </h1>
          <p className="text-sm sm:text-base text-ink-500">
            Your account, at a glance — secured and always yours.
          </p>
        </div>

        {/* Account summary — existing profile data only */}
        <div className="rounded-tile border border-ink-100 bg-white shadow-tile p-6 sm:p-8">
          <div className="grid gap-6 sm:grid-cols-3 sm:gap-8">
            <div className="space-y-1.5">
              <p className="text-[11px] font-semibold uppercase tracking-caps text-ink-500">
                Email
              </p>
              <p className="text-sm sm:text-base font-medium text-ink-900 break-all">
                {profile.email}
              </p>
            </div>
            <div className="space-y-1.5">
              <p className="text-[11px] font-semibold uppercase tracking-caps text-ink-500">
                Member since
              </p>
              <p className="text-sm sm:text-base font-medium text-ink-900">{memberSince}</p>
            </div>
            <div className="space-y-1.5">
              <p className="text-[11px] font-semibold uppercase tracking-caps text-ink-500">
                Member ID
              </p>
              <p className="text-xs font-mono text-ink-500 break-all pt-0.5">{profile.user_id}</p>
            </div>
          </div>
        </div>

        {/* Existing actions, presented as polished cards */}
        <div className="space-y-4">
          <h2 className="font-display text-xl sm:text-2xl font-bold tracking-display text-ink-900">
            Quick Actions
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Link
              href="/account"
              className="group rounded-tile border border-ink-100 bg-white p-6 shadow-tile transition-all duration-300 ease-luxe hover:shadow-tile-hover hover:-translate-y-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            >
              <p className="font-semibold text-ink-900">Account Settings</p>
              <p className="mt-1 text-sm text-ink-500">
                Review your details and manage your password.
              </p>
              <span
                aria-hidden="true"
                className="mt-4 inline-block text-sm font-medium text-accent-600 transition-transform duration-300 ease-luxe group-hover:translate-x-1"
              >
                Manage account →
              </span>
            </Link>

            <button
              type="button"
              onClick={handleSignOut}
              disabled={signingOut}
              className="group rounded-tile border border-ink-100 bg-white p-6 text-left shadow-tile transition-all duration-300 ease-luxe hover:shadow-tile-hover hover:-translate-y-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:opacity-50 disabled:pointer-events-none"
            >
              <p className="font-semibold text-ink-900">Sign Out</p>
              <p className="mt-1 text-sm text-ink-500">End your session on this device.</p>
              <span
                aria-hidden="true"
                className="mt-4 inline-block text-sm font-medium text-ink-500"
              >
                {signingOut ? 'Signing out...' : 'Log out of ShopSmart AI →'}
              </span>
            </button>
          </div>
        </div>
      </div>
    </AuthenticatedLayout>
  );
}
