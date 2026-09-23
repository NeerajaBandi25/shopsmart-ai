'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { login } from '@/lib/api-client';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Alert } from '@/components/ui/Alert';

interface LoginFormProps {
  onSuccess?: () => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const emailRef = useRef<HTMLInputElement>(null);

  // Focus the email input on mount
  useEffect(() => {
    emailRef.current?.focus();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess(null);
    setLoading(true);

    // Client-side validation
    if (!email) {
      setError('Email is required');
      setLoading(false);
      return;
    }

    if (!password) {
      setError('Password is required');
      setLoading(false);
      return;
    }

    try {
      const response = await login(email, password);
      onSuccess?.();

      // Show success message for 2 seconds, then redirect
      setSuccess('Login successful. Redirecting...');
      setTimeout(async () => {
        // Check if there's a redirect URL in query params, otherwise go to dashboard
        const urlParams = new URLSearchParams(window.location.search);
        const redirectTo = urlParams.get('redirectTo') || '/dashboard';
        router.push(redirectTo);
      }, 2000);
    } catch (err: any) {
      // Show generic error message (no email enumeration)
      setError(err.message || 'Invalid email or password');
      console.error('Login error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 w-full max-w-md">
      {/* Global messages */}
      {error && (
        <Alert variant="error" message={error} />
      )}
      {success && (
        <Alert variant="success" message={success} />
      )}

      {/* Email input */}
      <Input
        label="Email"
        value={email}
        onChange={setEmail}
        error={error ? 'Invalid email' : undefined}
        inputProps={{
          type: 'email',
          autoComplete: 'email',
          placeholder: 'you@example.com',
        }}
        inputRef={emailRef}
      />

      {/* Password input */}
      <Input
        label="Password"
        value={password}
        onChange={setPassword}
        error={error ? 'Invalid password' : undefined}
        inputProps={{
          type: 'password',
          autoComplete: 'current-password',
          placeholder: 'Enter your password',
        }}
      />

      {/* Submit button */}
      <Button
        variant="primary"
        size="md"
        className="w-full"
        disabled={loading}
        onClick={handleSubmit}
      >
        {loading ? 'Logging in...' : 'Log In'}
      </Button>

      {/* Link to register */}
      <p className="text-sm text-gray-600 text-center">
        Don't have an account?{' '}
        <a href="/auth/register" className="text-blue-600 hover:text-blue-700">
          Sign up
        </a>
      </p>
    </form>
  );
}