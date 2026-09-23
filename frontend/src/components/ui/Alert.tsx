import React from 'react';

interface AlertProps {
  variant?: 'success' | 'error' | 'warning' | 'info';
  message: string;
  className?: string;
}

export function Alert({
  variant = 'info',
  message,
  className = '',
}: AlertProps) {
  return (
    <div className={[
      'rounded-xl p-5',
      variant === 'success' && 'bg-green-50/50 text-green-800 dark:bg-green-900/20 dark:text-green-200 border border-green-200',
      variant === 'error' && 'bg-red-50/50 text-red-800 dark:bg-red-900/20 dark:text-red-200 border border-red-200',
      variant === 'warning' && 'bg-yellow-50/50 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-200 border border-yellow-200',
      variant === 'info' && 'bg-blue-50/50 text-blue-800 dark:bg-blue-900/20 dark:text-blue-200 border border-blue-200',
      className,
    ].join(' ')}>
      {message}
    </div>
  );
}