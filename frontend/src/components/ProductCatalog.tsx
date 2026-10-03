'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { getProducts, type Product, type ProductPage, type ProductQuery } from '@/lib/api-client';
import { AddToCartButton } from '@/components/AddToCartButton';
import { formatInr } from '@/lib/currency';

const PAGE_SIZE = 24;

const categoryImages: Record<string, string> = {
  accessories: '/images/Home-Page-Cat-Images/Accessories_main_cat.png',
  beauty: '/images/Home-Page-Cat-Images/BeautyPersonalCare_main_cat.png',
  fashion: '/images/Home-Page-Cat-Images/Fashion_main_cat.png',
  footwear: '/images/Home-Page-Cat-Images/Footwear_main_cat.png',
  home: '/images/Home-Page-Cat-Images/HomeLiving_main_cat.png',
  appliances: '/images/Home-Page-Cat-Images/KitchenDining_main_cat.png',
  laptops: '/images/Home-Page-Cat-Images/Electronics_main_cat.png',
  phones: '/images/Home-Page-Cat-Images/Electronics_main_cat.png',
  groceries: '/images/Home-Page-Cat-Images/KitchenDining_main_cat.png',
};

interface ProductCatalogProps {
  initialCategory?: string;
  initialSearch?: string;
}

export function ProductCatalog({
  initialCategory,
  initialSearch,
}: ProductCatalogProps) {
  const [skip, setSkip] = useState(0);
  const [filters, setFilters] = useState<ProductQuery>(() => ({
    category: initialCategory,
    q: initialSearch,
  }));
  const [search, setSearch] = useState(initialSearch || '');
  const [category, setCategory] = useState(initialCategory || '');
  const [brand, setBrand] = useState('');
  const [subcategory, setSubcategory] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [inStockOnly, setInStockOnly] = useState(false);
  const [sort, setSort] = useState<ProductQuery['sort']>('newest');
  const [retryCount, setRetryCount] = useState(0);
  const [page, setPage] = useState<ProductPage | null>(null);
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

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
    const parsedMaxPrice = maxPrice.trim() ? Number(maxPrice) : undefined;
    setSkip(0);
    setFilters({
      q: search.trim() || undefined,
      category: category || undefined,
      brand: brand.trim() || undefined,
      subcategory: subcategory.trim() || undefined,
      max_price_minor:
        parsedMaxPrice !== undefined && Number.isFinite(parsedMaxPrice)
          ? Math.round(parsedMaxPrice * 100)
          : undefined,
      in_stock_only: inStockOnly || undefined,
      sort,
    });
  }

  function clearFilters() {
    setSearch('');
    setCategory('');
    setBrand('');
    setSubcategory('');
    setMaxPrice('');
    setInStockOnly(false);
    setSort('newest');
    setFilters({});
    setSkip(0);
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
          className="mb-8 grid gap-3 border-y border-ink-100 py-5 sm:grid-cols-2 lg:grid-cols-[minmax(15rem,2fr)_repeat(5,minmax(0,1fr))_auto] lg:items-end"
        >
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
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
              <option value="laptops">Laptops</option>
              <option value="smartphones">Smartphones</option>
              <option value="headphones">Headphones</option>
              <option value="smartwatches">Smartwatches</option>
              <option value="tablets">Tablets</option>
              <option value="cameras">Cameras</option>
              <option value="televisions">Televisions</option>
              <option value="gaming">Gaming</option>
              <option value="home_appliances">Home appliances</option>
              <option value="kitchen_appliances">Kitchen appliances</option>
              <option value="accessories">Accessories</option>
              <option value="fashion">Fashion</option>
              <option value="footwear">Footwear</option>
              <option value="beauty">Beauty</option>
              <option value="home_living">Home &amp; living</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-700">
            Maximum price (₹)
            <input
              type="number"
              min="0"
              step="500"
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

        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <p aria-live="polite" className="text-sm text-ink-500">
            {status === 'success'
              ? `${total?.toLocaleString('en-IN') ?? `${observedEnd.toLocaleString('en-IN')}+`} products`
              : 'Products'}
          </p>
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
            No products match these filters.
          </p>
        )}

        {status === 'success' && products.length > 0 && (
          <div className="grid gap-x-4 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
            {products.map((product: Product) => {
              const categoryImage = categoryImages[product.category || ''];
              const image = product.image_url || categoryImage;

              return (
                <article
                  key={product.id}
                  className="flex min-w-0 flex-col overflow-hidden border-b border-ink-200 pb-5"
                >
                  <Link
                    href={`/products/${product.id}`}
                    aria-label={`View ${product.name} details`}
                    className="group relative mb-4 block aspect-[4/3] overflow-hidden bg-sand-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                  >
                    {image ? (
                      <Image
                        src={image}
                        alt={
                          product.image_url
                            ? product.image_alt || product.name
                            : `${product.category} category photograph; product-specific image unavailable`
                        }
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
                    {!product.image_url && categoryImage && (
                      <span className="absolute left-3 top-3 bg-white/90 px-2 py-1 text-[10px] font-semibold uppercase tracking-caps text-ink-700">
                        Category image
                      </span>
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
                  <div className="mt-4">
                    <AddToCartButton
                      productId={product.id}
                      stockQuantity={product.stock_quantity}
                      maxPurchaseQuantity={product.max_purchase_quantity}
                    />
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
              onClick={() => setSkip((currentSkip) => Math.max(0, currentSkip - PAGE_SIZE))}
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
