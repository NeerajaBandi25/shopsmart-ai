import React from 'react';

interface CardProps {
  className?: string;
  children: React.ReactNode;
}

export function Card({
  className = '',
  children,
}: CardProps) {
  return (
    <div className={`bg-white rounded-xl shadow-lg p-6 ${className}`}>
      {children}
    </div>
  );
}