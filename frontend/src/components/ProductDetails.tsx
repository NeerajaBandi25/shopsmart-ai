'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getProduct, type Product } from '@/lib/api-client';
import { formatInr } from '@/lib/currency';
import { ProductGallery } from '@/components/product-detail/ProductGallery';
import { ProductPurchaseActions } from '@/components/product-detail/ProductPurchaseActions';
import { RelatedProducts } from '@/components/product-detail/RelatedProducts';
import { categoryImageFor } from '@/components/product-detail/product-images';

interface ProductDetailsProps {
  productId: string;
}

export function ProductDetails({ productId }: ProductDetailsProps) {
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState('');
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let active = true;
    setProduct(null);
    setError('');

    getProduct(productId)
      .then((result) => {
        if (active) setProduct(result);
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(cause instanceof Error ? cause.message : 'Product details could not be loaded.');
        }
      });

    return () => {
      active = false;
    };
  }, [productId, retryCount]);

  if (error) {
    return (
      <section
        className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8"
        aria-labelledby="product-error-title"
      >
        <Link
          href="/products"
          className="text-sm font-semibold text-accent-700 underline underline-offset-4"
        >
          Back to products
        </Link>
        <div role="alert" className="mt-8 border-y border-ink-200 py-8">
          <h1 id="product-error-title" className="font-display text-2xl font-bold text-ink-900">
            Product unavailable
          </h1>
          <p className="mt-2 text-sm text-ink-500">
            {error.includes('not found') ? 'This product is no longer available.' : error}
          </p>
          <button
            type="button"
            onClick={() => setRetryCount((count) => count + 1)}
            className="mt-5 h-10 rounded-sm border border-ink-300 px-4 text-sm font-semibold text-ink-800 hover:bg-blush-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
          >
            Try again
          </button>
        </div>
      </section>
    );
  }

  if (!product) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8"
      >
        <p className="text-sm text-ink-500">Loading product…</p>
      </div>
    );
  }

  const categoryImage = categoryImageFor(product.category);
  const savings =
    product.list_price !== null && product.list_price > product.price
      ? product.list_price - product.price
      : 0;
  const discountPercent = savings ? Math.round((savings / product.list_price!) * 100) : 0;

  return (
    <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-12 lg:px-8">
      <Link
        href="/products"
        className="text-sm font-semibold text-accent-700 underline underline-offset-4"
      >
        Back to products
      </Link>
      <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(20rem,0.9fr)] lg:gap-14">
        <ProductGallery product={product} categoryImage={categoryImage} />

        <div className="flex flex-col">
          <p className="text-xs font-semibold uppercase tracking-caps text-accent-700">
            {product.brand || product.category || 'ShopSmart'}
          </p>
          <h1 className="mt-2 font-display text-3xl font-bold leading-tight text-ink-900 sm:text-4xl">
            {product.name}
          </h1>
          <p className="mt-2 text-xs uppercase tracking-caps text-ink-500">SKU {product.sku}</p>
          <div className="mt-6 border-y border-ink-200 py-5">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <p className="font-display text-2xl font-bold text-ink-900">
                {formatInr(product.price)}
              </p>
              {savings > 0 && (
                <>
                  <p className="text-base text-ink-500 line-through">
                    {formatInr(product.list_price!)}
                  </p>
                  <p className="text-sm font-semibold text-leaf-700">{discountPercent}% off</p>
                </>
              )}
            </div>
            {savings > 0 && (
              <p className="mt-1 text-sm text-leaf-700">You save {formatInr(savings)}</p>
            )}
            <p
              className={`mt-3 text-sm font-medium ${product.stock_quantity > 0 ? 'text-leaf-700' : 'text-ink-500'}`}
            >
              {product.stock_quantity > 0
                ? `${product.stock_quantity} in stock`
                : 'Currently out of stock'}
            </p>
            <p className="mt-2 text-xs leading-relaxed text-ink-500">
              Delivery availability and timing have not been provided for this listing.
            </p>
          </div>

          {product.description && (
            <p className="mt-6 text-base leading-relaxed text-ink-700">{product.description}</p>
          )}

          <section className="mt-7" aria-labelledby="product-highlights-title">
            <h2 id="product-highlights-title" className="text-sm font-semibold text-ink-900">
              Product highlights
            </h2>
            <dl className="mt-3 grid gap-x-6 gap-y-3 border-y border-ink-100 py-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs text-ink-500">Brand</dt>
                <dd className="mt-1 text-sm font-medium text-ink-800">
                  {product.brand || 'Not provided'}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-ink-500">Category</dt>
                <dd className="mt-1 text-sm font-medium capitalize text-ink-800">
                  {product.category || 'Not provided'}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-ink-500">SKU</dt>
                <dd className="mt-1 break-all text-sm font-medium text-ink-800">{product.sku}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-500">Purchase limit</dt>
                <dd className="mt-1 text-sm font-medium text-ink-800">
                  {product.max_purchase_quantity} per order
                </dd>
              </div>
            </dl>
          </section>

          {product.specifications && Object.keys(product.specifications).length > 0 && (
            <section className="mt-8" aria-labelledby="product-specifications-title">
              <h2 id="product-specifications-title" className="text-sm font-semibold text-ink-900">
                Specifications
              </h2>
              <dl className="mt-3 divide-y divide-ink-100 border-y border-ink-100">
                {Object.entries(product.specifications).map(([label, value]) => (
                  <div
                    key={label}
                    className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] gap-4 py-3 text-sm"
                  >
                    <dt className="text-ink-500">{label}</dt>
                    <dd className="break-words font-medium text-ink-800">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}

          <ProductPurchaseActions
            productId={product.id}
            stockQuantity={product.stock_quantity}
            maxPurchaseQuantity={product.max_purchase_quantity}
          />
          <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm">
            <Link
              href="/assistant"
              className="font-semibold text-accent-700 underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            >
              Ask ShopSmart AI
            </Link>
            <Link
              href="/cart"
              className="font-semibold text-ink-700 underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            >
              Eligible cart offers and final totals appear in your cart
            </Link>
          </div>
        </div>
      </div>
      <RelatedProducts product={product} />
    </section>
  );
}
