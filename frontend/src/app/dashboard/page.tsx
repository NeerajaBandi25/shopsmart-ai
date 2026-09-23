'use client';

import { useEffect, useState } from 'react';
import { getProfile } from '@/lib/api-client';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Card } from '@/components/ui/Card';
import AuthenticatedLayout from '@/app/authenticated-layout';

export default function DashboardPage() {
  const [profile, setProfile] = useState<null | {
    user_id: string;
    email: string;
    created_at: string;
  }>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    const loadProfile = async () => {
      try {
        setLoading(true);
        const data = await getProfile();
        setProfile(data);
        setError(null);
      } catch (err: any) {
        // Redirect to login if not authenticated
        setError(err.message || 'Failed to load profile');
        router.push('/auth/login');
      } finally {
        setLoading(false);
      }
    };

    loadProfile();
  }, [router]);

  if (loading) {
    // Show loading state within the authenticated layout
    return (
      <AuthenticatedLayout>
        <div className="flex flex-col items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </AuthenticatedLayout>
    );
  }

  if (error) {
    return (
      <AuthenticatedLayout>
        <div className="flex flex-col items-center justify-center py-8">
          <p className="text-red-600 text-center">{error}</p>
        </div>
      </AuthenticatedLayout>
    );
  }

  if (!profile) {
    // This state should not happen, but fallback to login
    router.push('/auth/login');
    return null;
  }

  return (
    <AuthenticatedLayout>
      <div className="space-y-8">
        {/* Welcome message */}
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome back, {profile.email.split('@')[0]}!
        </h1>

        {/* Profile Summary Card */}
        <Card className="space-y-4">
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-500">User ID</p>
            <p className="text-xl font-mono text-gray-900">{profile.user_id}</p>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-500">Email</p>
            <p className="text-xl font-mono break-all text-gray-900">
              {profile.email}
            </p>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-500">Member since</p>
            <p className="text-xl font-mono text-gray-900">
              {new Date(profile.created_at).toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </p>
          </div>
        </Card>

        {/* Quick Actions Section */}
        <div className="space-y-6">
          <h2 className="text-xl font-bold text-gray-900">
            Quick Actions
          </h2>
          <div className="space-y-4">
            <Link
              href="/account"
              className="w-full text-left text-sm font-medium text-gray-600 hover:text-gray-900"
            >
              View Account
            </Link>
          </div>
        </div>
      </div>
    </AuthenticatedLayout>
  );
}