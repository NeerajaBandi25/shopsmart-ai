import { act, fireEvent, render, screen } from '@testing-library/react';
import { RegistrationForm } from '@/components/registration-form';
import { register } from '@/lib/api-client';

jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn() }) }));
jest.mock('@/lib/api-client', () => ({ register: jest.fn() }));

const mockedRegister = jest.mocked(register);

describe('RegistrationForm', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockedRegister.mockReset();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  async function enterValidDetails() {
    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'shopper@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'ShopperPassword2026!' },
    });
    fireEvent.change(screen.getByLabelText('Confirm Password'), {
      target: { value: 'ShopperPassword2026!' },
    });
  }

  it('registers through the backend API client and shows success', async () => {
    mockedRegister.mockResolvedValue({
      user_id: 'user-1',
      email: 'shopper@example.com',
      created_at: '2026-09-26T00:00:00Z',
    });
    render(<RegistrationForm />);
    await enterValidDetails();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Create Account' }));
      await Promise.resolve();
    });

    expect(mockedRegister).toHaveBeenCalledWith('shopper@example.com', 'ShopperPassword2026!');
    expect(
      screen.getByText('Account created successfully. Redirecting to login...')
    ).toBeInTheDocument();
  });

  it('shows backend registration errors without labeling them as password mismatches', async () => {
    mockedRegister.mockRejectedValue(new Error('Registration service unavailable'));
    render(<RegistrationForm />);
    await enterValidDetails();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Create Account' }));
      await Promise.resolve();
    });

    expect(screen.getByText('Registration service unavailable')).toBeInTheDocument();
    expect(screen.queryByText('Passwords do not match')).not.toBeInTheDocument();
  });
});
