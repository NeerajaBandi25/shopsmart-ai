'use client';

import { Card } from '@/components/ui/Card';

export function DiscoverySection() {
  return (
    <section className="py-16 sm:py-20 lg:py-24 bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 className="mb-10 text-center text-2xl sm:text-3xl font-bold text-gray-900">
          AI-Powered Discovery Experience
        </h2>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <Card className="h-full flex flex-col items-center justify-center p-6 text-center hover:shadow-xl transition-shadow duration-300">
            <div className="text-4xl mb-3" aria-hidden="true">
              🤖
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">Smart Recommendations</h3>
            <p className="text-sm text-gray-600">
              Personalized suggestions based on your preferences and browsing history
            </p>
          </Card>

          <Card className="h-full flex flex-col items-center justify-center p-6 text-center hover:shadow-xl transition-shadow duration-300">
            <div className="text-4xl mb-3" aria-hidden="true">
              🔍
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">Visual Search</h3>
            <p className="text-sm text-gray-600">
              Find products using images or describe what you're looking for in natural language
            </p>
          </Card>

          <Card className="h-full flex flex-col items-center justify-center p-6 text-center hover:shadow-xl transition-shadow duration-300">
            <div className="text-4xl mb-3" aria-hidden="true">
              📊
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">Trend Analysis</h3>
            <p className="text-sm text-gray-600">
              Stay ahead of fashion and lifestyle trends with AI-powered insights
            </p>
          </Card>
        </div>
        <p className="mt-10 text-center text-sm text-gray-500 max-w-xl mx-auto">
          Conceptual features demonstrating our AI vision. These capabilities are
          planned for future implementation and are not currently available.
        </p>
      </div>
    </section>
  );
}