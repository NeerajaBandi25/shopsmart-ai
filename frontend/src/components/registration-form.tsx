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

  const isPasswordStrong = Object.values(passwordStrength).every(v => v);

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
        onChange={(value) => {
          setPassword(value);
          validatePasswordStrength(value);
        }}
        error={error ? 'Invalid password' : undefined}
        inputProps={{
          type: 'password',
          autoComplete: 'new-password',
          placeholder: 'Enter strong password',
        }}
      />

      {/* Password strength indicator */}
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

      {/* Confirm password input */}
      <Input
        label="Confirm Password"
        value={confirmPassword}
        onChange={setConfirmPassword}
        error={error ? 'Passwords do not match' : undefined}
        inputProps={{
          type: 'password',
          autoComplete: 'new-password',
          placeholder: 'Confirm password',
        }}
      />

      {/* Submit button */}
      <Button
        variant="primary"
        size="md"
        className="w-full"
        disabled={loading || !isPasswordStrong}
        onClick={handleSubmit}
      >
        {loading ? 'Creating account...' : 'Create Account'}
      </Button>

      {/* Link to login */}
      <p className="text-sm text-gray-600 text-center">
        Already have an account?{' '}
        <a href="/auth/login" className="text-blue-600 hover:text-blue-700">
          Log in
        </a>
      </p>
    </form>
  );
}