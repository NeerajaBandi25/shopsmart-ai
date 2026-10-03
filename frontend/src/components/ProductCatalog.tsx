'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import {
  getHomepage,
  getProducts,
  type HomepageData,
  type Product,
  type ProductPage,
  type ProductQuery,
} from '@/lib/api-client';
import { CompareButton } from '@/components/ShoppingTools';
import { catalogUrl, interpretCatalogSearch, readCatalogQuery } from '@/lib/catalog-query';
import { AddToCartButton } from '@/components/AddToCartButton';
import { formatInr } from '@/lib/currency';

const PAGE_SIZE = 24;

interface ProductCatalogProps {
  initialCategory?: string;
  initialSearch?: string;
  initialFilters?: ProductQuery;
  initialSkip?: number;
}

export function ProductCatalog({
  initialCategory,
  initialSearch,
  initialFilters,
  initialSkip = 0,
}: ProductCatalogProps) {
  const editedRef = useRef(false);
  const startingFilters = interpretCatalogSearch(
    initialFilters || { category: initialCategory, q: initialSearch },
    []
  );
  const [skip, setSkip] = useState(initialSkip);
  const [categories, setCategories] = useState<HomepageData['categories']>([]);
  const [filters, setFilters] = useState<ProductQuery>(startingFilters);
  const [search, setSearch] = useState(startingFilters.q || '');
  const [category, setCategory] = useState(startingFilters.category || '');
  const [brand, setBrand] = useState(startingFilters.brand || '');
  const [subcategory, setSubcategory] = useState(startingFilters.subcategory || '');
  const [maxPrice, setMaxPrice] = useState(
    startingFilters.max_price_minor === undefined
      ? ''
      : String(startingFilters.max_price_minor / 100)
  );
  const [minPrice, setMinPrice] = useState(
    startingFilters.min_price_minor === undefined
      ? ''
      : String(startingFilters.min_price_minor / 100)
  );
  const [inStockOnly, setInStockOnly] = useState(!!startingFilters.in_stock_only);
  const [sort, setSort] = useState<ProductQuery['sort']>(startingFilters.sort || 'newest');
  const [retryCount, setRetryCount] = useState(0);
  const [page, setPage] = useState<ProductPage | null>(null);
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [filterError, setFilterError] = useState('');

  function restoreFilters(next: ProductQuery) {
    setFilters(next);
    setSearch(next.q || '');
    setCategory(next.category || '');
    setBrand(next.brand || '');
    setSubcategory(next.subcategory || '');
    setMinPrice(next.min_price_minor === undefined ? '' : String(next.min_price_minor / 100));
    setMaxPrice(next.max_price_minor === undefined ? '' : String(next.max_price_minor / 100));
    setInStockOnly(!!next.in_stock_only);
    setSort(next.sort || 'newest');
  }

  useEffect(() => {
    let active = true;
    getHomepage()
      .then((data) => {
        if (!active) return;
        setCategories(data.categories);
        const next = interpretCatalogSearch(startingFilters, data.categories);
        if (!editedRef.current && JSON.stringify(next) !== JSON.stringify(startingFilters)) {
          restoreFilters(next);
          window.history.replaceState(null, '', catalogUrl(next, initialSkip));
        }
      })
      .catch(() => {});
    const restore = () => {
      editedRef.current = true;
      const params = Object.fromEntries(new URLSearchParams(window.location.search));
      restoreFilters(readCatalogQuery(params));
      const restoredSkip = Number(params.skip);
      setSkip(Number.isSafeInteger(restoredSkip) && restoredSkip > 0 ? restoredSkip : 0);
    };
    window.addEventListener('popstate', restore);
    return () => {
      active = false;
      window.removeEventListener('popstate', restore);
    };
    // Initial route props are hydrated once; subsequent browser history restores the URL state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function changePage(nextSkip: number) {
    editedRef.current = true;
    setSkip(nextSkip);
    window.history.pushState(null, '', catalogUrl(filters, nextSkip));
  }

  useEffect(() => {
    let currentRequest = true;
    setStatus('loading');
    setErrorMessage('');

    getProducts(skip, PAGE_SIZE, filters)
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
  }, [filters, retryCount, skip]);

  function applyFilters(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    editedRef.current = true;
    const parsedMaxPrice = maxPrice.trim() ? Number(maxPrice) : undefined;
    const parsedMinPrice = minPrice.trim() ? Number(minPrice) : undefined;
    if (
      [parsedMinPrice, parsedMaxPrice].some(
        (value) =>
          value !== undefined && (value < 0 || !Number.isSafeInteger(Math.round(value * 100)))
      ) ||
      (parsedMinPrice !== undefined &&
        parsedMaxPrice !== undefined &&
        parsedMinPrice > parsedMaxPrice)
    ) {
      setFilterError('Enter a valid price range. Minimum price must not exceed maximum price.');
      return;
    }
    setFilterError('');
    setSkip(0);
    const next = interpretCatalogSearch(
      {
        q: search.trim() || undefined,
        category: category || undefined,
        brand: brand.trim() || undefined,
        subcategory: subcategory.trim() || undefined,
        min_price_minor:
          parsedMinPrice === undefined ? undefined : Math.round(parsedMinPrice * 100),
        max_price_minor:
          parsedMaxPrice !== undefined && Number.isFinite(parsedMaxPrice)
            ? Math.round(parsedMaxPrice * 100)
            : undefined,
        in_stock_only: inStockOnly || undefined,
        sort,
      },
      categories
    );
    restoreFilters(next);
    window.history.pushState(null, '', catalogUrl(next, 0));
  }

  function clearFilters() {
    editedRef.current = true;
    setFilterError('');
    setSearch('');
    setCategory('');
    setBrand('');
    setSubcategory('');
    setMaxPrice('');
    setMinPrice('');
    setInStockOnly(false);
    setSort('newest');
    setFilters({});
    setSkip(0);
    window.history.pushState(null, '', '/products');
  }

  const products = page?.items ?? [];
  const hasPreviousPage = skip > 0;
  const observedEnd = skip + products.length;
  const total =
    typeof page?.total === 'number'
      ? page.total
      : products.length < PAGE_SIZE
        ? observedEnd
        : undefined;
  const hasNextPage =
    status === 'success' &&
    (total === undefined ? products.length === PAGE_SIZE : observedEnd < total);

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
            Browse current offers with prices in Indian rupees and live stock availability.
          </p>
          <Link
            href="/cart"
            className="mt-2 w-fit text-sm font-semibold text-accent-700 underline underline-offset-4"
          >
            View cart
          </Link>
        </div>

        <form
          onSubmit={applyFilters}
          className="mb-8 grid grid-cols-2 gap-3 border-y border-ink-100 py-5 lg:grid-cols-4 lg:items-end"
        >
          <label className="col-span-2 flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
            Search products
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Try “laptop”"
              className="h-11 w-full rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 placeholder:text-ink-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
            Brand
            <input
              type="search"
              value={brand}
              onChange={(event) => setBrand(event.target.value)}
              placeholder="Any brand"
              className="h-11 w-full rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 placeholder:text-ink-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
            Subcategory
            <input
              type="search"
              value={subcategory}
              onChange={(event) => setSubcategory(event.target.value)}
              placeholder="Any subcategory"
              className="h-11 w-full rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 placeholder:text-ink-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
            Category
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              className="h-11 w-full rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            >
              <option value="">All categories</option>
              {categories.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
              {category && !categories.some((item) => item.value === category) && (
                <option value={category}>{category.replace(/_/g, ' ')}</option>
              )}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
            Minimum price (₹)
            <input
              type="number"
              min="0"
              step="0.01"
              value={minPrice}
              onChange={(event) => setMinPrice(event.target.value)}
              placeholder="Any price"
              className="h-11 w-full rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 focus-visible:ring-2 focus-visible:ring-accent-500"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
            Maximum price (₹)
            <input
              type="number"
              min="0"
              step="0.01"
              value={maxPrice}
              onChange={(event) => setMaxPrice(event.target.value)}
              placeholder="Any price"
              className="h-11 w-full rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 placeholder:text-ink-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
            Sort by
            <select
              value={sort}
              onChange={(event) => setSort(event.target.value as ProductQuery['sort'])}
              className="h-11 w-full rounded-sm border border-ink-300 bg-white px-3 text-sm font-normal text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            >
              <option value="newest">Newest</option>
              <option value="price_asc">Price: low to high</option>
              <option value="price_desc">Price: high to low</option>
              <option value="name_asc">Name</option>
            </select>
          </label>
          <label className="flex h-11 items-center gap-2 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={inStockOnly}
              onChange={(event) => setInStockOnly(event.target.checked)}
              className="h-4 w-4 accent-leaf-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            />
            In stock
          </label>
          <div className="flex items-end gap-2 sm:col-span-2 lg:col-span-1">
            <button
              type="submit"
              className="h-11 rounded-sm bg-accent-700 px-4 text-sm font-semibold text-white hover:bg-accent-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
            >
              Apply
            </button>
            <button
              type="button"
              onClick={clearFilters}
              className="h-11 px-2 text-sm font-semibold text-ink-700 underline underline-offset-4 hover:text-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
            >
              Clear
            </button>
          </div>
        </form>
        {filterError && (
          <p role="alert" className="mb-6 text-sm text-accent-800">
            {filterError}
          </p>
        )}

        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <p aria-live="polite" className="text-sm text-ink-500">
            {status === 'success'
              ? `${total?.toLocaleString('en-IN') ?? `${observedEnd.toLocaleString('en-IN')}+`} products`
              : 'Products'}
          </p>
        </div>

        <Link
          href={
            '/assistant?q=' +
            encodeURIComponent(
              [search, category.replace(/_/g, ' '), maxPrice ? 'under INR ' + maxPrice : '']
                .filter(Boolean)
                .join(' ')
            )
          }
          className="mb-5 inline-flex min-h-11 items-center text-sm font-semibold text-accent-700 underline underline-offset-4"
        >
          Need help with your shortlist? Ask the shopping assistant
        </Link>

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
            No products match these filters.
          </p>
        )}

        {status === 'success' && products.length > 0 && (
          <div className="grid gap-x-4 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
            {products.map((product: Product) => {
              const image = product.image_url;

              return (
                <article
                  key={product.id}
                  className="flex min-w-0 flex-col overflow-hidden rounded-2xl border border-sand-200 bg-white p-3 shadow-tile"
                >
                  <Link
                    href={`/products/${product.id}`}
                    aria-label={`View ${product.name} details`}
                    className="group relative mb-4 block aspect-[4/3] overflow-hidden rounded-xl bg-sand-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                  >
                    {image ? (
                      <Image
                        src={image}
                        alt={product.image_alt || product.name}
                        fill
                        sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
                        className="object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                      />
                    ) : (
                      <div
                        role="img"
                        aria-label="Product image unavailable"
                        className="absolute inset-0 grid place-items-center bg-sand-100 p-4 text-center text-xs font-semibold uppercase tracking-caps text-ink-500"
                      >
                        Product image unavailable
                      </div>
                    )}
                  </Link>
                  <div className="flex flex-1 flex-col">
                    <p className="text-[11px] font-semibold uppercase tracking-caps text-ink-500">
                      {product.brand || product.category || 'ShopSmart'}
                    </p>
                    <Link
                      href={`/products/${product.id}`}
                      className="mt-1 w-fit focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                    >
                      <h3 className="font-display text-xl font-bold text-ink-900">
                        {product.name}
                      </h3>
                    </Link>
                    {product.description && (
                      <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-ink-500">
                        {product.description}
                      </p>
                    )}
                  </div>
                  <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
                    <div className="flex items-baseline gap-2">
                      <p className="font-semibold text-ink-900">{formatInr(product.price)}</p>
                      {product.list_price !== null && product.list_price > product.price && (
                        <p className="text-sm text-ink-500 line-through">
                          {formatInr(product.list_price)}
                        </p>
                      )}
                    </div>
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
                  <div className="mt-4 flex flex-wrap gap-2">
                    <AddToCartButton
                      productId={product.id}
                      stockQuantity={product.stock_quantity}
                      maxPurchaseQuantity={product.max_purchase_quantity}
                    />
                    <CompareButton productId={product.id} />
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {status === 'success' && (hasPreviousPage || hasNextPage) && (
          <nav aria-label="Product pages" className="mt-8 flex items-center justify-between gap-4">
            <button
              type="button"
              onClick={() => changePage(Math.max(0, skip - PAGE_SIZE))}
              disabled={!hasPreviousPage}
              className="rounded-sm border border-ink-300 px-4 py-2 text-sm font-semibold text-ink-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Previous
            </button>
            <p className="text-center text-xs text-ink-500">
              Products {skip + 1}–{observedEnd}
              {total === undefined ? '+' : ` of ${total.toLocaleString('en-IN')}`}
            </p>
            <button
              type="button"
              onClick={() => changePage(skip + PAGE_SIZE)}
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
