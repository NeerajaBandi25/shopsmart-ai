import { act, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import AccountPage from './page';

const mockPush = jest.fn();
const mockRouter = { push: mockPush };

jest.mock('next/navigation', () => ({
  useRouter: () => mockRouter,
}));

jest.mock('@/app/authenticated-layout', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => children,
}));

jest.mock('@/lib/api-client', () => ({
  ...jest.requireActual('@/lib/api-client'),
  getProfile: jest.fn(),
  changePassword: jest.fn(),
  logout: jest.fn(),
}));

import { changePassword, getProfile, logout } from '@/lib/api-client';

describe('AccountPage password change', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getProfile as jest.Mock).mockResolvedValue({
      user_id: 'user-1',
      email: 'test@example.com',
      created_at: '2026-09-27T00:00:00Z',
    });
    (changePassword as jest.Mock).mockResolvedValue(undefined);
    (logout as jest.Mock).mockRejectedValue(new Error('Session already invalidated'));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('returns the user to login after password change invalidates the current session', async () => {
    const consoleError = jest.spyOn(console, 'error').mockImplementation(() => undefined);
    render(<AccountPage />);

    await screen.findByRole('heading', { name: 'Account Information' });
    jest.useFakeTimers();
    fireEvent.change(screen.getByLabelText('Current Password'), {
      target: { value: 'CurrentPassword123!' },
    });
    fireEvent.change(screen.getByLabelText('New Password'), {
      target: { value: 'NewPassword456!' },
    });
    fireEvent.change(screen.getByLabelText('Confirm New Password'), {
      target: { value: 'NewPassword456!' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Change Password' }));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(
      screen.getByText('Password changed successfully. You will be logged out.')
    ).toBeInTheDocument();
    expect(changePassword).toHaveBeenCalledWith('CurrentPassword123!', 'NewPassword456!');

    await act(async () => {
      jest.advanceTimersByTime(2000);
      await Promise.resolve();
    });
    expect(logout).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith('/auth/login');
    consoleError.mockRestore();
  });

  it('keeps the password form available and announces a mismatch once', async () => {
    render(<AccountPage />);

    await screen.findByRole('heading', { name: 'Account Information' });
    fireEvent.change(screen.getByLabelText('Current Password'), {
      target: { value: 'CurrentPassword123!' },
    });
    fireEvent.change(screen.getByLabelText('New Password'), {
      target: { value: 'NewPassword456!' },
    });
    fireEvent.change(screen.getByLabelText('Confirm New Password'), {
      target: { value: 'DifferentPassword789!' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Change Password' }));

    expect(screen.getByRole('heading', { name: 'Account Information' })).toBeInTheDocument();
    expect(screen.getByLabelText('Confirm New Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Change Password' })).toBeInTheDocument();
    expect(screen.getAllByRole('alert')).toHaveLength(1);
    expect(screen.getByRole('alert')).toHaveTextContent('New passwords do not match');
    expect(changePassword).not.toHaveBeenCalled();
  });
});
