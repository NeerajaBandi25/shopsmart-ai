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
      await login(email, password);
      onSuccess?.();

      // Show success message for 2 seconds, then redirect
      setSuccess('Login successful. Redirecting...');
      setTimeout(async () => {
        // Check if there's a redirect URL in query params, otherwise go to dashboard
        const urlParams = new URLSearchParams(window.location.search);
        const redirectTo = urlParams.get('redirectTo') || '/dashboard';
        router.push(redirectTo);
      }, 2000);
    } catch (err) {
      // Show generic error message (no email enumeration)
      setError(
        err instanceof Error ? err.message : 'Invalid email or password'
      );
      console.error('Login error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Premium field styling applied through the existing Input component's
  // extension points (className wrapper + inputProps classes). ui/Input.tsx
  // itself remains frozen.
  const fieldClassName = 'premium-field';
  const fieldInputClasses =
    'border-ink-100! bg-white! rounded-tile! shadow-tile! focus:ring-accent-500! focus-visible:ring-accent-500! transition-shadow!';

  return (
    <form onSubmit={handleSubmit} className="space-y-5 w-full max-w-md">
      {/* Global messages */}
      {error && (
        <Alert variant="error" message={error} />
      )}
      {success && (
        <Alert variant="success" message={success} />
      )}

      {/* Email input — real errors are shown in the Alert above; do not
          stamp misleading per-field messages for server-side errors. */}
      <Input
        label="Email"
        value={email}
        onChange={setEmail}
        className={fieldClassName}
        inputProps={{
          type: 'email',
          autoComplete: 'email',
          placeholder: 'you@example.com',
          className: fieldInputClasses,
        }}
        inputRef={emailRef}
      />

      {/* Password input */}
      <Input
        label="Password"
        value={password}
        onChange={setPassword}
        className={fieldClassName}
        inputProps={{
          type: 'password',
          autoComplete: 'current-password',
          placeholder: 'Enter your password',
          className: fieldInputClasses,
        }}
      />

      {/* Submit button */}
      <Button
        variant="primary"
        size="md"
        className="w-full bg-accent-600! hover:bg-accent-700! focus-visible:ring-accent-500! focus-visible:ring-offset-2! rounded-tile! py-3!"
        disabled={loading}
        onClick={handleSubmit}
      >
        {loading ? 'Logging in...' : 'Log In'}
      </Button>

      {/* Link to register */}
      <p className="text-sm text-ink-500 text-center">
        Don&apos;t have an account?{' '}
        <a href="/auth/register" className="font-medium text-accent-600 hover:text-accent-700">
          Sign up
        </a>
      </p>
    </form>
  );
}
