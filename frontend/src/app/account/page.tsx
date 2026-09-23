'use client';

import { useState, useEffect } from 'react';
import { getProfile, logout, changePassword } from '@/lib/api-client';
import { useRouter } from 'next/navigation';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Alert } from '@/components/ui/Alert';
import AuthenticatedLayout from '@/app/authenticated-layout';

export default function AccountPage() {
  const [profile, setProfile] = useState<null | {
    user_id: string;
    email: string;
    created_at: string;
  }>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [passwordChangeLoading, setPasswordChangeLoading] = useState(false);
  const router = useRouter();

  // Profile loading
  useEffect(() => {
    const loadProfile = async () => {
      try {
        setLoading(true);
        const data = await getProfile();
        setProfile(data);
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to load profile');
        router.push('/auth/login');
      } finally {
        setLoading(false);
      }
    };

    loadProfile();
  }, [router]);

  // Handle password change
  const handlePasswordChange = async (
    e: React.FormEvent<HTMLFormElement>
  ) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setPasswordChangeLoading(true);

    const formData = new FormData(e.currentTarget);
    const currentPassword = formData.get('currentPassword') as string;
    const newPassword = formData.get('newPassword') as string;
    const confirmPassword = formData.get('confirmPassword') as string;

    // Client-side validation
    if (!currentPassword) {
      setError('Current password is required');
      setPasswordChangeLoading(false);
      return;
    }
    if (!newPassword) {
      setError('New password is required');
      setPasswordChangeLoading(false);
      return;
    }
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters');
      setPasswordChangeLoading(false);
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match');
      setPasswordChangeLoading(false);
      return;
    }

    try {
      // Call the password change API
      await changePassword(currentPassword, newPassword);

      // Success: show success message, then logout
      setSuccess('Password changed successfully. You will be logged out.');
      e.currentTarget.reset();

      // Logout after a short delay to let the user see the message
      setTimeout(async () => {
        try {
          await logout();
        } catch (logoutErr) {
          console.error('Logout error:', logoutErr);
        }
        router.push('/auth/login');
      }, 2000);
    } catch (err: any) {
      setError(err.message || 'An error occurred. Please try again.');
    } finally {
      setPasswordChangeLoading(false);
    }
  };

  if (loading) {
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
          <Alert variant="error" message={error} />
        </div>
      </AuthenticatedLayout>
    );
  }

  if (!profile) {
    // Fallback
    router.push('/auth/login');
    return null;
  }

  return (
    <AuthenticatedLayout>
      <div className="space-y-8">
        {/* Profile Information Section */}
        <Card className="space-y-6">
          <h1 className="text-2xl font-bold text-gray-900">Account Information</h1>
          <div className="space-y-4">
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
          </div>
        </Card>

        {/* Password Change Form Section */}
        <Card className="space-y-6">
          <h1 className="text-2xl font-bold text-gray-900">Change Password</h1>
          <form onSubmit={handlePasswordChange} className="space-y-6">
            {/* Current Password */}
            <Input
              label="Current Password"
              value=""
              onChange={(e) => {}} // handled via formdata
              error={error ? 'Current password is required' : undefined}
              inputProps={{
                type: 'password',
                id: 'currentPassword',
                autoComplete: 'current-password',
                required: true,
              }}
            />

            {/* New Password */}
            <Input
              label="New Password"
              value=""
              onChange={(e) => {}} // handled via formdata
              error={
                error &&
                (error.includes('New password') || error.includes('Passwords do not match'))
                  ? error
                  : undefined
              }
              inputProps={{
                type: 'password',
                id: 'newPassword',
                autoComplete: 'new-password',
                required: true,
                minLength: 8,
              }}
            />

            {/* Confirm New Password */}
            <Input
              label="Confirm New Password"
              value=""
              onChange={(e) => {}} // handled via formdata
              error={
                error && error.includes('Passwords do not match')
                  ? error
                  : undefined
              }
              inputProps={{
                type: 'password',
                id: 'confirmPassword',
                autoComplete: 'new-password',
                required: true,
              }}
            />

            {/* Error Message */}
            {error && (
              <Alert variant="error" message={error} className="mt-4" />
            )}

            {/* Success Message */}
            {success && (
              <Alert variant="success" message={success} className="mt-4" />
            )}

            <Button
              type="submit"
              variant="primary"
              size="md"
              className="w-full"
              disabled={passwordChangeLoading}
            >
              {passwordChangeLoading ? 'Saving...' : 'Change Password'}
            </Button>
          </form>
        </Card>

        {/* Sign Out Alternative */}
        <div className="mt-8">
          <Button
            variant="danger"
            size="md"
            onClick={async () => {
              try {
                await logout();
                router.push('/auth/login');
              } catch (err) {
                console.error('Logout error:', err);
              }
            }}
          >
            Sign Out
          </Button>
        </div>
      </div>
    </AuthenticatedLayout>
  );
}