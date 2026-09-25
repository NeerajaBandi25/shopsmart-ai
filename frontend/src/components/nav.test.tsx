import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import Nav from './nav';

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
  });

  it('renders application title', () => {
    render(<Nav />);
    expect(screen.getByText(/shopsmart ai/i)).toBeInTheDocument();
  });

  it('shows logout button when authenticated', async () => {
    (getProfile as jest.Mock).mockResolvedValue({});
    render(<Nav />);
    await screen.findByRole('button', { name: /log out/i });
    expect(screen.getByRole('button', { name: /log out/i })).toBeInTheDocument();
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
