'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

interface RegistrationFormProps {
  onSuccess?: () => void;
}

export function RegistrationForm({ onSuccess }: RegistrationFormProps) {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [passwordStrength, setPasswordStrength] = useState<{
    length: boolean;
    uppercase: boolean;
    lowercase: boolean;
    digit: boolean;
    special: boolean;
  }>({
    length: false,
    uppercase: false,
    lowercase: false,
    digit: false,
    special: false,
  });

  const validatePasswordStrength = (pwd: string) => {
    setPasswordStrength({
      length: pwd.length >= 8,
      uppercase: /[A-Z]/.test(pwd),
      lowercase: /[a-z]/.test(pwd),
      digit: /\d/.test(pwd),
      special: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(pwd),
    });
  };

  const isPasswordStrong = Object.values(passwordStrength).every(v => v);

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const pwd = e.target.value;
    setPassword(pwd);
    validatePasswordStrength(pwd);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Client-side validation
    if (!email) {
      setError('Email is required');
      setLoading(false);
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }

    if (!isPasswordStrong) {
      setError('Password does not meet strength requirements');
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/auth/register`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ email, password }),
        }
      );

      if (response.ok) {
        onSuccess?.();
        router.push('/auth/login?message=Account%20created%20successfully%20—%20please%20log%20in');
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Registration failed');
      }
    } catch (err) {
      setError('An error occurred. Please try again.');
      console.error('Registration error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 w-full max-w-md">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      <div>
        <label htmlFor="email" className="block text-sm font-medium text-gray-700">
          Email
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
          className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
          placeholder="you@example.com"
        />
      </div>

      <div>
        <label htmlFor="password" className="block text-sm font-medium text-gray-700">
          Password
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={handlePasswordChange}
          required
          className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
          placeholder="Enter strong password"
        />
        <div className="mt-2 text-sm space-y-1">
          <div
            className={`flex items-center ${
              passwordStrength.length ? 'text-green-600' : 'text-gray-400'
            }`}
          >
            {passwordStrength.length ? '✓' : '○'} At least 8 characters
          </div>
          <div
            className={`flex items-center ${
              passwordStrength.uppercase ? 'text-green-600' : 'text-gray-400'
            }`}
          >
            {passwordStrength.uppercase ? '✓' : '○'} Uppercase letter
          </div>
          <div
            className={`flex items-center ${
              passwordStrength.lowercase ? 'text-green-600' : 'text-gray-400'
            }`}
          >
            {passwordStrength.lowercase ? '✓' : '○'} Lowercase letter
          </div>
          <div
            className={`flex items-center ${
              passwordStrength.digit ? 'text-green-600' : 'text-gray-400'
            }`}
          >
            {passwordStrength.digit ? '✓' : '○'} Number
          </div>
          <div
            className={`flex items-center ${
              passwordStrength.special ? 'text-green-600' : 'text-gray-400'
            }`}
          >
            {passwordStrength.special ? '✓' : '○'} Special character
          </div>
        </div>
      </div>

      <div>
        <label
          htmlFor="confirmPassword"
          className="block text-sm font-medium text-gray-700"
        >
          Confirm Password
        </label>
        <input
          id="confirmPassword"
          type="password"
          value={confirmPassword}
          onChange={e => setConfirmPassword(e.target.value)}
          required
          className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
          placeholder="Confirm password"
        />
      </div>

      <button
        type="submit"
        disabled={loading || !isPasswordStrong}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-2 px-4 rounded transition"
      >
        {loading ? 'Creating account...' : 'Create Account'}
      </button>

      <p className="text-sm text-gray-600 text-center">
        Already have an account?{' '}
        <a href="/auth/login" className="text-blue-600 hover:text-blue-700">
          Log in
        </a>
      </p>
    </form>
  );
}
