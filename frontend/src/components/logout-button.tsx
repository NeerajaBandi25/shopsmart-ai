'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { logout } from '@/lib/api-client';

interface LogoutButtonProps {
  onSuccess?: () => void;
  className?: string;
}

export function LogoutButton({ onSuccess, className }: LogoutButtonProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const handleClick = async () => {
    setLoading(true);
    setError(false);

    try {
      await logout();
      onSuccess?.();
      router.push('/auth/login');
    } catch (err) {
      console.error('Logout error:', err);
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button
        onClick={handleClick}
        disabled={loading}
        className={`w-full bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white font-semibold py-2 px-4 rounded transition ${className ?? ''}`}
      >
        {loading ? 'Logging out...' : 'Log Out'}
      </button>
      {error && <p role="alert">Logout failed. Please try again.</p>}
    </>
  );
}
