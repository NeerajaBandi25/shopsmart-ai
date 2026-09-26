'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getProducts, type Product, type ProductPage } from '@/lib/api-client';
import { AddToCartButton } from '@/components/AddToCartButton';

const PAGE_SIZE = 24;
const priceFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
});

export function ProductCatalog() {
  const [skip, setSkip] = useState(0);
  const [retryCount, setRetryCount] = useState(0);
  const [page, setPage] = useState<ProductPage | null>(null);
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    let currentRequest = true;
    setStatus('loading');
    setErrorMessage('');

    getProducts(skip, PAGE_SIZE)
      .then((result) => {
        if (currentRequest) {
          setPage(result);
          setStatus('success');
        }
      })
      .catch((error: unknown) => {
        if (currentRequest) {
          setErrorMessage(error instanceof Error ? error.message : 'Products could not be loaded.');
          setStatus('error');
        }
      });

    return () => {
      currentRequest = false;
    };
  }, [retryCount, skip]);

  const products = page?.items ?? [];
  const hasPreviousPage = skip > 0;
  const hasNextPage = status === 'success' && products.length === PAGE_SIZE;

  return (
    <section aria-labelledby="product-catalog-title" className="border-y border-ink-100 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <div className="mb-8 flex flex-col gap-2 sm:mb-10">
          <p className="text-xs font-semibold uppercase tracking-caps text-accent-600">
            Available now
          </p>
          <h2
            id="product-catalog-title"
            className="font-display text-display-md font-bold text-ink-900 sm:text-display-lg"
          >
            Shop the Edit
          </h2>
          <p className="max-w-xl text-sm text-ink-500">
            Current products, with live pricing and stock availability.
          </p>
          <Link
            href="/cart"
            className="mt-2 w-fit text-sm font-semibold text-accent-700 underline underline-offset-4"
          >
            View cart
          </Link>
        </div>

        {status === 'loading' && (
          <div role="status" aria-live="polite" className="rounded-tile border border-ink-100 p-6">
            <p className="text-sm text-ink-500">Loading products...</p>
          </div>
        )}

        {status === 'error' && (
          <div role="alert" className="rounded-tile border border-status-error/30 bg-red-50 p-6">
            <p className="font-medium text-ink-900">Products could not be loaded.</p>
            <p className="mt-1 text-sm text-ink-500">{errorMessage}</p>
            <button
              type="button"
              onClick={() => setRetryCount((count) => count + 1)}
              className="mt-4 rounded-sm bg-accent-700 px-4 py-2 text-sm font-semibold text-white hover:bg-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
            >
              Try again
            </button>
          </div>
        )}

        {status === 'success' && products.length === 0 && (
          <p className="rounded-tile border border-ink-100 bg-blush-50 px-6 py-10 text-center text-ink-500">
            No products are available yet.
          </p>
        )}

        {status === 'success' && products.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {products.map((product: Product) => (
              <article
                key={product.id}
                className="flex min-h-52 flex-col rounded-tile border border-ink-100 bg-blush-50/60 p-5 sm:p-6"
              >
                <div className="flex-1">
                  <p className="text-[11px] font-semibold uppercase tracking-caps text-ink-500">
                    SKU {product.sku}
                  </p>
                  <h3 className="mt-2 font-display text-xl font-bold text-ink-900">
                    {product.name}
                  </h3>
                  {product.description && (
                    <p className="mt-2 text-sm leading-relaxed text-ink-500">
                      {product.description}
                    </p>
                  )}
                </div>
                <div className="mt-5 flex items-end justify-between gap-3 border-t border-ink-100 pt-4">
                  <p className="font-semibold text-ink-900">
                    {priceFormatter.format(product.price / 100)}
                  </p>
                  <p
                    className={`text-right text-xs font-medium ${
                      product.stock_quantity > 0 ? 'text-leaf-700' : 'text-ink-500'
                    }`}
                  >
                    {product.stock_quantity > 0
                      ? `${product.stock_quantity} in stock`
                      : 'Out of stock'}
                  </p>
                </div>
                <div className="mt-4">
                  <AddToCartButton
                    productId={product.id}
                    stockQuantity={product.stock_quantity}
                    maxPurchaseQuantity={product.max_purchase_quantity}
                  />
                </div>
              </article>
            ))}
          </div>
        )}

        {status === 'success' && (hasPreviousPage || hasNextPage) && (
          <nav aria-label="Product pages" className="mt-8 flex items-center justify-between gap-4">
            <button
              type="button"
              onClick={() => setSkip((currentSkip) => Math.max(0, currentSkip - PAGE_SIZE))}
              disabled={!hasPreviousPage}
              className="rounded-sm border border-ink-300 px-4 py-2 text-sm font-semibold text-ink-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Previous
            </button>
            <p className="text-center text-xs text-ink-500">
              Products {skip + 1}–{skip + products.length}
            </p>
            <button
              type="button"
              onClick={() => setSkip((currentSkip) => currentSkip + PAGE_SIZE)}
              disabled={!hasNextPage}
              className="rounded-sm border border-ink-300 px-4 py-2 text-sm font-semibold text-ink-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
            </button>
          </nav>
        )}
      </div>
    </section>
  );
}
