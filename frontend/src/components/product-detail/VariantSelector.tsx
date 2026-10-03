'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getProducts, type Product } from '@/lib/api-client';
import { formatInr } from '@/lib/currency';

export function VariantSelector({ product }: { product: Product }) {
  const [variants, setVariants] = useState<Product[]>([]);
  useEffect(() => {
    let active = true;
    const familyName = product.name.split(',')[0];
    getProducts(0, 16, {
      q: familyName,
      category: product.category || undefined,
      brand: product.brand || undefined,
    })
      .then((page) => {
        if (active)
          setVariants(page.items.filter((item) => item.name.split(',')[0] === familyName));
      })
      .catch(() => {
        if (active) setVariants([]);
      });
    return () => {
      active = false;
    };
  }, [product.id, product.name, product.brand, product.category]);
  if (variants.length < 2) return null;
  return (
    <section className="mt-6" aria-labelledby="variant-heading">
      <h2 id="variant-heading" className="text-sm font-semibold text-ink-900">
        Choose your configuration
      </h2>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {variants.map((variant) => (
          <Link
            key={variant.id}
            href={`/products/${variant.id}`}
            aria-current={variant.id === product.id ? 'page' : undefined}
            className={`min-h-11 rounded-lg border p-3 text-xs leading-relaxed focus-visible:ring-2 focus-visible:ring-accent-500 ${variant.id === product.id ? 'border-accent-600 bg-blush-50' : 'border-ink-200 hover:border-ink-500'}`}
          >
            <span className="block font-medium">
              {String(variant.specifications?.Variant || variant.name)}
            </span>
            <span className="mt-1 block text-ink-500">
              {formatInr(variant.price)} · {variant.stock_quantity > 0 ? 'In stock' : 'Sold out'}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
