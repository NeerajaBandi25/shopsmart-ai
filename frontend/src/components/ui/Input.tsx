import React from 'react';

interface InputProps {
  type?: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  disabled?: boolean;
  className?: string;
  inputProps?: Omit<React.InputHTMLAttributes<HTMLInputElement>, 'ref'>;
  inputRef?: React.Ref<HTMLInputElement>;
}

export function Input({
  type = 'text',
  label,
  value,
  onChange,
  error,
  disabled = false,
  className = '',
  inputProps,
  inputRef,
}: InputProps) {
  return (
    <div className={className}>
      <label
        htmlFor={label.toLowerCase().replace(/\s+/g, '-')}
        className="mb-2 block text-sm font-medium text-gray-700"
      >
        {label}
      </label>
      <input
        type={type}
        id={label.toLowerCase().replace(/\s+/g, '-')}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        ref={inputRef}
        className={[
          'w-full px-4 py-3 border border-gray-200 rounded-md shadow-sm',
          'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'error:border-red-500',
        ].join(' ')}
        {...inputProps}
      />
      {error && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
