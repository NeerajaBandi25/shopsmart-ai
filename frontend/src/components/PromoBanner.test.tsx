import { render, screen, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { PromoBanner } from './PromoBanner';

describe('PromoBanner navigation', () => {
  it('links Get Started to registration', () => {
    render(<PromoBanner />);

    expect(screen.getByRole('link', { name: 'Get Started' })).toHaveAttribute(
      'href',
      '/auth/register'
    );
  });

  it('links the promo Sign In action to login', () => {
    render(<PromoBanner />);

    expect(screen.getByRole('link', { name: 'Sign In' })).toHaveAttribute('href', '/auth/login');
  });

  it('links footer navigation to the expected destinations', () => {
    render(<PromoBanner />);
    const footerNavigation = within(screen.getByRole('navigation', { name: 'Footer' }));

    expect(footerNavigation.getByRole('link', { name: 'Home' })).toHaveAttribute('href', '/');
    expect(footerNavigation.getByRole('link', { name: 'Sign in' })).toHaveAttribute(
      'href',
      '/auth/login'
    );
    expect(footerNavigation.getByRole('link', { name: 'Create account' })).toHaveAttribute(
      'href',
      '/auth/register'
    );
  });
});
