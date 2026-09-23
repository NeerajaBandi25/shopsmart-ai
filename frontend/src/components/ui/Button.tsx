import React from 'react';

interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  disabled?: boolean;
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
  type?: React.ButtonHTMLAttributes<HTMLButtonElement>['type'];
  children: React.ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  disabled = false,
  onClick,
  type = 'button',
  children,
}: ButtonProps) {
  // Base classes
  const baseClasses = `
    focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2
    focus-visible:ring-primary-500
    disabled:opacity-50 disabled:pointer-events-none
    transition-all duration-200
    hover:scale-[1.03]
    active:scale-[0.98]
  `;

  // Variant classes
  const variantClasses = {
    primary: `
      bg-primary-600 text-white hover:bg-primary-700 focus:ring-primary-500/20
    `,
    secondary: `
      bg-transparent text-primary-600 hover:bg-primary-50 border border-primary-600 hover:border-transparent
      focus:ring-primary-500/20
    `,
    danger: `
      bg-transparent text-red-600 hover:bg-red-50 border border-red-600 hover:border-transparent
      focus:ring-red-500/20
    `,
  };

  // Size classes
  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm font-medium',
    md: 'px-4 py-2 text-base font-medium',
    lg: 'px-6 py-3 text-lg font-medium',
  };

  return (
    <button
      type={type}
      className={[
        baseClasses,
        variantClasses[variant as keyof typeof variantClasses],
        sizeClasses[size as keyof typeof sizeClasses],
        className,
      ].join(' ')}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}