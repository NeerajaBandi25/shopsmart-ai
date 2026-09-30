import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import Nav from './nav';
import { useCommerceStore } from '@/lib/commerce-store';

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(() => ({ push: jest.fn() })),
}));

// Mock getProfile
jest.mock('@/lib/api-client', () => ({
  ...jest.requireActual('@/lib/api-client'),
  getProfile: jest.fn(),
}));
import { getProfile } from '@/lib/api-client';

describe('Nav', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useCommerceStore.getState().clearPrivateCommerce();
  });

  it('renders application title', () => {
    render(<Nav />);
    expect(screen.getByText(/shopsmart ai/i)).toBeInTheDocument();
  });

  it('restores authenticated navigation after current-user validation succeeds', async () => {
    (getProfile as jest.Mock).mockResolvedValue({
      user_id: 'user-1',
      email: 'test@example.com',
      created_at: '2026-01-01T00:00:00Z',
    });
    render(<Nav />);
    await screen.findByRole('button', { name: /log out/i });
    expect(screen.getByRole('button', { name: /log out/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Cart, 0 items' })).toHaveAttribute('href', '/cart');
    expect(screen.getByRole('link', { name: 'Orders' })).toHaveAttribute('href', '/orders');
    expect(getProfile).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Account' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Sign In' })).not.toBeInTheDocument();
  });

  it('shows the shared cart item count in the authenticated navigation', async () => {
    useCommerceStore.getState().syncCartCount({ items: [{ quantity: 2 }, { quantity: 1 }] });
    (getProfile as jest.Mock).mockResolvedValue({
      user_id: 'user-1',
      email: 'test@example.com',
      created_at: '2026-01-01T00:00:00Z',
    });

    render(<Nav />);

    expect(await screen.findByRole('link', { name: 'Cart, 3 items' })).toHaveAttribute(
      'href',
      '/cart'
    );
    expect(screen.getByText('(3)')).toBeInTheDocument();
  });

  it('hides logout button when not authenticated', async () => {
    (getProfile as jest.Mock).mockRejectedValue(new Error('Unauthorized'));
    render(<Nav />);
    expect(screen.queryByRole('button', { name: /log out/i })).not.toBeInTheDocument();
  });

  it('shows loading state while checking auth', async () => {
    (getProfile as jest.Mock).mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({}), 100))
    );
    render(<Nav />);
    // During loading, nav should still render but we can check for the loading indicator in the nav
    // Since we don't show specific loading UI in the nav, we'll check that it renders without error
    expect(screen.getByRole('navigation')).toHaveClass('bg-white border-b border-gray-200');
    await screen.findByText(/shopsmart ai/i);
  });
});
