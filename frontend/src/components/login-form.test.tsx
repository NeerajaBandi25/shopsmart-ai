import { act, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { LoginForm } from './login-form';

const mockPush = jest.fn();
const mockRouter = { push: mockPush };

jest.mock('next/navigation', () => ({
  useRouter: () => mockRouter,
}));

jest.mock('@/lib/api-client', () => ({
  ...jest.requireActual('@/lib/api-client'),
  login: jest.fn(),
}));

import { login } from '@/lib/api-client';

describe('LoginForm', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('submits through the form and redirects after login succeeds', async () => {
    (login as jest.Mock).mockResolvedValue({
      user_id: 'user-1',
      email: 'member@example.com',
    });
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'member@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'StrongPassword123!' },
    });
    const submitButton = screen.getByRole('button', { name: 'Log In' });
    expect(submitButton).toHaveAttribute('type', 'submit');

    await act(async () => {
      fireEvent.submit(submitButton.closest('form')!);
      await Promise.resolve();
    });

    expect(login).toHaveBeenCalledWith('member@example.com', 'StrongPassword123!');
    expect(screen.getByText('Login successful. Redirecting...')).toBeInTheDocument();

    await act(async () => {
      jest.advanceTimersByTime(2000);
      await Promise.resolve();
    });
    expect(mockPush).toHaveBeenCalledWith('/dashboard');
  });

  it('shows a failed-login message without navigating', async () => {
    const consoleError = jest.spyOn(console, 'error').mockImplementation(() => undefined);
    (login as jest.Mock).mockRejectedValue(new Error('Invalid email or password'));
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'member@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'wrong' },
    });

    await act(async () => {
      fireEvent.submit(screen.getByRole('button', { name: 'Log In' }).closest('form')!);
      await Promise.resolve();
    });

    expect(screen.getByText('Invalid email or password')).toBeInTheDocument();
    expect(mockPush).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });
});
