'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Alert } from '@/components/ui/Alert';

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
  const [success, setSuccess] = useState<string | null>(null);
  const emailRef = useRef<HTMLInputElement>(null);

  // Focus the email input on mount
  useEffect(() => {
    emailRef.current?.focus();
  }, []);

  const validatePasswordStrength = (pwd: string) => {
    setPasswordStrength({
      length: pwd.length >= 8,
      uppercase: /[A-Z]/.test(pwd),
      lowercase: /[a-z]/.test(pwd),
      digit: /\d/.test(pwd),
      special: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(pwd),
    });
  };

  const isPasswordStrong = Object.values(passwordStrength).every((v) => v);

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
      // Same-origin call — proxied to the backend by next.config.mjs.
      const response = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      if (response.ok) {
        onSuccess?.();
        // Show success message for 2 seconds, then redirect to login with success message
        setSuccess('Account created successfully. Redirecting to login...');
        setTimeout(() => {
          router.push('/auth/login?message=Account%20created%20successfully');
        }, 2000);
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

  // Premium field styling applied through the existing Input component's
  // extension points (className wrapper + inputProps classes). ui/Input.tsx
  // itself remains frozen.
  const fieldClassName = 'premium-field';
  const fieldInputClasses =
    'border-ink-100! bg-white! rounded-tile! shadow-tile! focus:ring-accent-500! focus-visible:ring-accent-500! transition-shadow!';

  const strengthItems = [
    { ok: passwordStrength.length, label: 'At least 8 characters' },
    { ok: passwordStrength.uppercase, label: 'Uppercase letter' },
    { ok: passwordStrength.lowercase, label: 'Lowercase letter' },
    { ok: passwordStrength.digit, label: 'Number' },
    { ok: passwordStrength.special, label: 'Special character' },
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-5 w-full max-w-md">
      {/* Global messages */}
      {error && <Alert variant="error" message={error} />}
      {success && <Alert variant="success" message={success} />}

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
        onChange={(value) => {
          setPassword(value);
          validatePasswordStrength(value);
        }}
        className={fieldClassName}
        inputProps={{
          type: 'password',
          autoComplete: 'new-password',
          placeholder: 'Enter strong password',
          className: fieldInputClasses,
        }}
      />

      {/* Password strength indicator */}
      <div
        className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5 text-sm"
        aria-label="Password requirements"
      >
        {strengthItems.map((item) => (
          <div
            key={item.label}
            className={`flex items-center gap-2 transition-colors duration-200 ${
              item.ok ? 'text-status-success' : 'text-ink-300'
            }`}
          >
            <span aria-hidden="true">{item.ok ? '✓' : '○'}</span>
            {item.label}
          </div>
        ))}
      </div>

      {/* Confirm password input */}
      <Input
        label="Confirm Password"
        value={confirmPassword}
        onChange={setConfirmPassword}
        error={error ? 'Passwords do not match' : undefined}
        className={fieldClassName}
        inputProps={{
          type: 'password',
          autoComplete: 'new-password',
          placeholder: 'Confirm password',
          className: fieldInputClasses,
        }}
      />

      {/* Submit button */}
      <Button
        variant="primary"
        size="md"
        className="w-full bg-accent-600! hover:bg-accent-700! focus-visible:ring-accent-500! focus-visible:ring-offset-2! rounded-tile! py-3!"
        disabled={loading || !isPasswordStrong}
        onClick={handleSubmit}
      >
        {loading ? 'Creating account...' : 'Create Account'}
      </Button>

      {/* Link to login */}
      <p className="text-sm text-ink-500 text-center">
        Already have an account?{' '}
        <a href="/auth/login" className="font-medium text-accent-600 hover:text-accent-700">
          Log in
        </a>
      </p>
    </form>
  );
}
