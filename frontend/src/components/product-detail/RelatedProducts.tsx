'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { getProducts, type Product } from '@/lib/api-client';
import { formatInr } from '@/lib/currency';
import { categoryImageFor } from '@/components/product-detail/product-images';

interface RelatedProductsProps {
  product: Product;
}

function comparisonValue(product: Product, key: string): string {
  if (key === 'Price') return formatInr(product.price);
  if (key === 'List price')
    return product.list_price ? formatInr(product.list_price) : 'Not provided';
  if (key === 'Brand') return product.brand || 'Not provided';
  if (key === 'Category') return product.category || 'Not provided';
  if (key === 'Availability') {
    return product.stock_quantity > 0 ? `${product.stock_quantity} in stock` : 'Out of stock';
  }
  const value = product.specifications?.[key];
  return value === undefined ? 'Not provided' : String(value);
}

export function RelatedProducts({ product }: RelatedProductsProps) {
  const [items, setItems] = useState<Product[]>([]);
  const [selected, setSelected] = useState<Product | null>(null);
  const [status, setStatus] = useState<'loading' | 'success' | 'empty' | 'error'>(
    product.category ? 'loading' : 'empty'
  );
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setSelected(null);
    if (!product.category) {
      setItems([]);
      setStatus('empty');
      return () => {
        active = false;
      };
    }

    setStatus('loading');
    getProducts(0, 8, { category: product.category })
      .then((page) => {
        if (!active) return;
        const related = page.items.filter(
          (item) => item.id !== product.id && item.category === product.category
        );
        setItems(related);
        setStatus(related.length ? 'success' : 'empty');
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(cause instanceof Error ? cause.message : 'Related products could not be loaded.');
        setStatus('error');
      });

    return () => {
      active = false;
    };
  }, [product.category, product.id]);

  const specificationKeys = selected
    ? Array.from(
        new Set([
          ...Object.keys(product.specifications || {}).filter((key) => !key.startsWith('_')),
          ...Object.keys(selected.specifications || {}).filter((key) => !key.startsWith('_')),
        ])
      )
    : [];
  const comparisonRows = [
    'Price',
    'List price',
    'Brand',
    'Category',
    'Availability',
    ...specificationKeys,
  ];

  return (
    <section
      className="mt-14 border-t border-ink-200 pt-8"
      aria-labelledby="related-products-title"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-caps text-accent-700">
            More to explore
          </p>
          <h2
            id="related-products-title"
            className="mt-1 font-display text-2xl font-bold text-ink-900"
          >
            Related products
          </h2>
        </div>
        {status === 'success' && <p className="text-sm text-ink-500">Same category</p>}
      </div>

      {status === 'loading' && (
        <p role="status" className="mt-6 text-sm text-ink-500">
          Loading related products...
        </p>
      )}
      {status === 'error' && (
        <p role="status" className="mt-6 text-sm text-ink-500">
          Related products are unavailable right now. {error}
        </p>
      )}
      {status === 'empty' && (
        <p className="mt-6 text-sm text-ink-500">
          {product.category
            ? 'No other products in this category are available to show.'
            : 'Related products are unavailable because this listing has no category.'}
        </p>
      )}
      {status === 'success' && (
        <div className="mt-6 grid gap-x-4 gap-y-7 sm:grid-cols-2 lg:grid-cols-4">
          {items.map((item) => {
            const fallback = categoryImageFor(item.category);
            const image = item.image_url || fallback;
            return (
              <article key={item.id} className="min-w-0 border-b border-ink-200 pb-4">
                <Link
                  href={`/products/${item.id}`}
                  aria-label={`View ${item.name} details`}
                  className="relative mb-3 block aspect-[4/3] overflow-hidden bg-sand-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                >
                  {image ? (
                    <Image
                      src={image}
                      alt={
                        item.image_url
                          ? item.image_alt || item.name
                          : `${item.category} category photograph; product-specific image unavailable`
                      }
                      fill
                      sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
                      className={item.image_url ? 'object-contain p-3' : 'object-cover'}
                    />
                  ) : (
                    <span
                      role="img"
                      aria-label="Product image unavailable"
                      className="grid h-full place-items-center p-4 text-center text-xs text-ink-500"
                    >
                      Product image unavailable
                    </span>
                  )}
                  {!item.image_url && fallback && (
                    <span className="absolute left-2 top-2 bg-white/90 px-2 py-1 text-[10px] font-semibold uppercase tracking-caps text-ink-700">
                      Category image
                    </span>
                  )}
                </Link>
                <p className="text-xs font-semibold uppercase tracking-caps text-ink-500">
                  {item.brand || item.category || 'ShopSmart'}
                </p>
                <Link
                  href={`/products/${item.id}`}
                  className="mt-1 inline-block font-semibold text-ink-900 underline-offset-4 hover:underline"
                >
                  {item.name}
                </Link>
                <p className="mt-2 font-semibold text-ink-900">{formatInr(item.price)}</p>
                <button
                  type="button"
                  onClick={() => setSelected((current) => (current?.id === item.id ? null : item))}
                  aria-pressed={selected?.id === item.id}
                  className="mt-3 text-sm font-semibold text-accent-700 underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                >
                  {selected?.id === item.id ? 'Remove comparison' : 'Compare with this product'}
                </button>
              </article>
            );
          })}
        </div>
      )}

      {selected && (
        <section className="mt-8" aria-labelledby="product-comparison-title">
          <h3 id="product-comparison-title" className="font-display text-xl font-bold text-ink-900">
            Compare products
          </h3>
          <div className="mt-3 overflow-x-auto border-y border-ink-200">
            <table className="w-full min-w-[34rem] border-collapse text-left text-sm">
              <thead>
                <tr>
                  <th scope="col" className="w-36 py-3 pr-4 font-medium text-ink-500">
                    Detail
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold text-ink-900">
                    {product.name}
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold text-ink-900">
                    {selected.name}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {comparisonRows.map((key) => (
                  <tr key={key}>
                    <th scope="row" className="py-3 pr-4 font-medium text-ink-500">
                      {key}
                    </th>
                    <td className="px-4 py-3 text-ink-800">{comparisonValue(product, key)}</td>
                    <td className="px-4 py-3 text-ink-800">{comparisonValue(selected, key)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </section>
  );
}
