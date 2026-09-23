'use client';

import { CategoryCard } from '@/components/ui/CategoryCard';

export function CategorySection() {
  const categories = [
    { name: 'Fashion', icon: '👗' },
    { name: 'Electronics', icon: '📱' },
    { name: 'Home & Living', icon: '🏠' },
    { name: 'Beauty & Personal Care', icon: '💄' },
    { name: 'Sports & Outdoors', icon: '⚽' }
  ];

  return (
    <section className="py-16 sm:py-20 lg:py-24">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 className="mb-8 text-center text-2xl sm:text-3xl font-bold text-gray-900">
          Explore by Category
        </h2>
        <div className="relative">
          {/* Horizontal scroll on mobile, grid on desktop */}
          <div className="overflow-x-auto space-x-4 sm:hidden pb-4">
            <div className="flex space-x-4">
              {categories.map((category, index) => (
                <CategoryCard key={index} {...category} />
              ))}
            </div>
          </div>

          {/* Grid layout on desktop and up */}
          <div className="hidden sm:flex sm:grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 sm:gap-8">
            {categories.map((category, index) => (
              <CategoryCard key={index} {...category} />
            ))}
          </div>
        </div>
        <p className="mt-8 text-center text-sm text-gray-500 max-w-xl mx-auto">
          Visual categories for browsing inspiration. Actual shopping functionality
          is not yet implemented - this section showcases our design vision.
        </p>
      </div>
    </section>
  );
}