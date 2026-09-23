'use client';

import React from 'react';
import { Card } from '@/components/ui/Card';

interface CategoryCardProps {
  name: string;
  icon: string;
}

export function CategoryCard({ name, icon }: CategoryCardProps) {
  return (
    <Card className="flex-shrink-0 w-40 sm:w-44 md:w-48 text-center hover:shadow-xl transition-shadow duration-300 cursor-default">
      <div className="space-y-2">
        <div className="text-4xl sm:text-5xl md:text-6xl" aria-hidden="true">
          {icon}
        </div>
        <h3 className="font-semibold text-gray-900 text-sm sm:text-base leading-tight">
          {name}
        </h3>
      </div>
    </Card>
  );
}