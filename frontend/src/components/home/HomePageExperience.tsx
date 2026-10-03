'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { AddToCartButton } from '@/components/AddToCartButton';
import { formatInr } from '@/lib/currency';
import { getProducts, type Product } from '@/lib/api-client';

const CATEGORIES = [
  { label: 'Laptops', value: 'laptops', note: 'Work and play' },
  { label: 'Smartphones', value: 'smartphones', note: 'Mobile essentials' },
  { label: 'Headphones', value: 'headphones', note: 'Sound for every day' },
  { label: 'Smartwatches', value: 'smartwatches', note: 'A closer look at your day' },
  { label: 'Tablets', value: 'tablets', note: 'Portable screens and tools' },
  { label: 'Cameras', value: 'cameras', note: 'Make a frame of it' },
  { label: 'Televisions', value: 'televisions', note: 'Room-filling picture' },
  { label: 'Gaming', value: 'gaming', note: 'Play your way' },
  { label: 'Home appliances', value: 'home_appliances', note: 'Useful by design' },
  { label: 'Kitchen appliances', value: 'kitchen_appliances', note: 'Everyday kitchen tools' },
  { label: 'Fashion', value: 'fashion', note: 'Everyday expression' },
  { label: 'Footwear', value: 'footwear', note: 'Find your fit' },
  { label: 'Beauty', value: 'beauty', note: 'Daily rituals' },
  { label: 'Accessories', value: 'accessories', note: 'The finishing touch' },
  { label: 'Home & living', value: 'home_living', note: 'Make your space yours' },
];

function ProductTile({ product }: { product: Product }) {
  const hasDiscount = product.list_price !== null && product.list_price > product.price;

  return (
    <article className="flex min-w-0 flex-col border-b border-ink-200 pb-5">
      <Link
        href={`/products/${encodeURIComponent(product.id)}`}
        aria-label={`View ${product.name} details`}
        className="group relative mb-4 block aspect-[4/3] overflow-hidden bg-sand-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
      >
        {product.image_url ? (
          <Image
            src={product.image_url}
            alt={product.image_alt || product.name}
            fill
            sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
            className="object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          />
        ) : (
          <div
            role="img"
            aria-label={`${product.name}; product image unavailable`}
            className="absolute inset-0 grid place-items-center bg-blush-50 px-5 text-center font-display text-lg text-ink-500"
          >
            {product.category || 'Shop the catalog'}
          </div>
        )}
        {hasDiscount && (
          <span className="absolute left-3 top-3 bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-caps text-accent-800">
            Listed offer
          </span>
        )}
      </Link>

      <div className="flex flex-1 flex-col">
        <p className="text-[11px] font-semibold uppercase tracking-caps text-ink-500">
          {product.brand || product.category || 'ShopSmart'}
        </p>
        <Link
          href={`/products/${encodeURIComponent(product.id)}`}
          className="mt-1 w-fit focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
        >
          <h3 className="font-display text-lg font-bold text-ink-900">{product.name}</h3>
        </Link>
        {product.description && (
          <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-ink-500">
            {product.description}
          </p>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <p className="font-semibold text-ink-900">{formatInr(product.price)}</p>
        {hasDiscount && (
          <>
            <p className="text-sm text-ink-500 line-through">{formatInr(product.list_price!)}</p>
            <p className="text-xs font-medium text-leaf-700">
              Save {formatInr(product.list_price! - product.price)}
            </p>
          </>
        )}
        <p className="ml-auto text-right text-xs text-ink-500">
          {product.stock_quantity > 0 ? `${product.stock_quantity} in stock` : 'Out of stock'}
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
}

export function HomePageExperience() {
  const [products, setProducts] = useState<Product[]>([]);
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    setStatus('loading');

    getProducts(0, 24, { sort: 'newest' })
      .then((page) => {
        if (active) {
          setProducts(page.items);
          setStatus('success');
        }
      })
      .catch(() => {
        if (active) setStatus('error');
      });

    return () => {
      active = false;
    };
  }, [retry]);

  const featuredProducts = products.filter((product) => product.stock_quantity > 0).slice(0, 8);
  const deals = products.filter(
    (product) =>
      product.stock_quantity > 0 &&
      product.list_price !== null &&
      product.list_price > product.price
  );

  return (
    <>
      <main>
        <section className="relative overflow-hidden bg-ink-900 text-white">
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-[radial-gradient(ellipse_at_80%_15%,rgba(195,126,158,0.28),transparent_40%),linear-gradient(115deg,transparent_48%,rgba(62,107,79,0.24)_100%)]"
          />
          <div className="relative mx-auto grid min-h-[34rem] max-w-7xl items-center gap-10 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-[1.1fr_0.9fr] lg:px-8 lg:py-24">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-caps text-accent-300">
                ShopSmart AI · The everyday edit
              </p>
              <h1 className="mt-5 font-display text-5xl font-bold leading-[1.02] text-balance sm:text-6xl">
                Good finds. Thoughtfully gathered.
              </h1>
              <p className="mt-5 max-w-lg text-base leading-relaxed text-ink-200 sm:text-lg">
                Explore the current catalog, compare listed prices, and find something useful for
                your day.
              </p>
              <form action="/products" method="get" className="mt-8 flex max-w-xl gap-2">
                <label className="sr-only" htmlFor="home-product-search">
                  Search products
                </label>
                <input
                  id="home-product-search"
                  type="search"
                  name="q"
                  placeholder="Search products"
                  className="h-12 min-w-0 flex-1 rounded-sm border border-white/25 bg-white px-4 text-sm text-ink-900 placeholder:text-ink-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-300"
                />
                <button
                  type="submit"
                  className="h-12 shrink-0 rounded-sm bg-accent-500 px-5 text-sm font-semibold text-white transition-colors hover:bg-accent-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-ink-900"
                >
                  Search
                </button>
              </form>
              <Link
                href="/assistant"
                className="mt-5 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-white underline decoration-accent-300 underline-offset-4 hover:text-accent-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
              >
                Ask the shopping assistant <span aria-hidden="true">→</span>
              </Link>
            </div>

            <div className="relative hidden min-h-[22rem] items-end justify-end border-l border-white/15 pl-8 lg:flex">
              <div aria-hidden="true" className="absolute inset-8 border border-accent-300/35" />
              <div
                aria-hidden="true"
                className="absolute right-16 top-10 h-40 w-40 rounded-full border border-white/20"
              />
              <div className="relative max-w-sm pb-5">
                <p className="font-display text-4xl font-semibold leading-tight">
                  A little more considered.
                </p>
                <p className="mt-4 max-w-xs text-sm leading-relaxed text-ink-200">
                  Browse actual listings with product details, current prices, and stock shown at a
                  glance.
                </p>
                <Link
                  href="/products"
                  className="mt-6 inline-flex min-h-11 items-center border-b border-accent-300 text-sm font-semibold text-white hover:text-accent-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
                >
                  Explore all products{' '}
                  <span aria-hidden="true" className="ml-3">
                    ↗
                  </span>
                </Link>
              </div>
            </div>
          </div>
        </section>

        <section aria-labelledby="category-heading" className="border-b border-ink-100 bg-white">
          <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-caps text-accent-700">
                  Start somewhere
                </p>
                <h2
                  id="category-heading"
                  className="mt-2 font-display text-3xl font-bold text-ink-900"
                >
                  Browse by category
                </h2>
              </div>
              <Link
                href="/products"
                className="text-sm font-semibold text-ink-700 underline underline-offset-4 hover:text-accent-700"
              >
                View the full catalog
              </Link>
            </div>
            <nav
              aria-label="Product categories"
              className="mt-7 grid grid-cols-2 gap-x-6 sm:grid-cols-3 lg:grid-cols-5"
            >
              {CATEGORIES.map((category, index) => (
                <Link
                  key={category.value}
                  href={`/products?category=${encodeURIComponent(category.value)}`}
                  className="group flex min-h-24 items-center gap-3 border-t border-ink-200 py-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                >
                  <span aria-hidden="true" className="font-display text-2xl text-accent-700">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span>
                    <span className="block text-sm font-semibold text-ink-900 group-hover:text-accent-700">
                      {category.label}
                    </span>
                    <span className="mt-1 block text-xs text-ink-500">{category.note}</span>
                  </span>
                </Link>
              ))}
            </nav>
          </div>
        </section>

        <section aria-labelledby="featured-heading" className="bg-blush-50">
          <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-caps text-accent-700">
                  From the latest listings
                </p>
                <h2
                  id="featured-heading"
                  className="mt-2 font-display text-3xl font-bold text-ink-900"
                >
                  In the catalog now
                </h2>
              </div>
              <Link
                href="/products"
                className="text-sm font-semibold text-ink-700 underline underline-offset-4 hover:text-accent-700"
              >
                Shop all products
              </Link>
            </div>

            {status === 'loading' && (
              <p role="status" className="mt-8 border-y border-ink-200 py-6 text-sm text-ink-500">
                Loading current products…
              </p>
            )}
            {status === 'error' && (
              <div role="alert" className="mt-8 border-y border-ink-200 py-6">
                <p className="text-sm text-ink-700">Current products could not be loaded.</p>
                <button
                  type="button"
                  onClick={() => setRetry((attempt) => attempt + 1)}
                  className="mt-3 text-sm font-semibold text-accent-700 underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                >
                  Try again
                </button>
              </div>
            )}
            {status === 'success' && featuredProducts.length === 0 && (
              <p className="mt-8 border-y border-ink-200 py-6 text-sm text-ink-500">
                No in-stock products are listed at the moment.
              </p>
            )}
            {status === 'success' && featuredProducts.length > 0 && (
              <div className="mt-8 grid gap-x-5 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
                {featuredProducts.map((product) => (
                  <ProductTile key={product.id} product={product} />
                ))}
              </div>
            )}
          </div>
        </section>

        {status === 'success' && deals.length > 0 && (
          <section aria-labelledby="deals-heading" className="border-y border-ink-100 bg-white">
            <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-caps text-leaf-700">
                    Current catalog pricing
                  </p>
                  <h2
                    id="deals-heading"
                    className="mt-2 font-display text-3xl font-bold text-ink-900"
                  >
                    Listed offers
                  </h2>
                  <p className="mt-2 text-sm text-ink-500">
                    Items shown here have a listed price above their current price.
                  </p>
                </div>
                <Link
                  href="/products"
                  className="text-sm font-semibold text-ink-700 underline underline-offset-4 hover:text-accent-700"
                >
                  Browse the catalog
                </Link>
              </div>
              <div className="mt-8 grid gap-x-5 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
                {deals.slice(0, 4).map((product) => (
                  <ProductTile key={product.id} product={product} />
                ))}
              </div>
            </div>
          </section>
        )}

        <section aria-labelledby="shopping-details-heading" className="bg-leaf-900 text-white">
          <div className="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-3 lg:px-8">
            <h2 id="shopping-details-heading" className="font-display text-2xl font-bold">
              Useful details, up front.
            </h2>
            <p className="text-sm leading-relaxed text-white/80">
              Product prices are displayed in Indian rupees using the current catalog listing.
            </p>
            <p className="text-sm leading-relaxed text-white/80">
              Stock availability and product details are shown from the product listing. Check the
              item page for its full information.
            </p>
          </div>
        </section>
      </main>

      <footer className="bg-ink-900 text-ink-300">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-10 sm:px-6 md:grid-cols-[1.5fr_1fr_1fr] lg:px-8">
          <div>
            <Link href="/" className="font-display text-xl font-bold text-white">
              ShopSmart <span className="text-accent-300">AI</span>
            </Link>
            <p className="mt-3 max-w-sm text-sm leading-relaxed">
              A considered place to explore everyday products, current prices, and useful details.
            </p>
          </div>
          <nav aria-label="Footer shopping links">
            <h2 className="text-xs font-semibold uppercase tracking-caps text-accent-300">Shop</h2>
            <ul className="mt-4 space-y-3 text-sm">
              <li>
                <Link href="/products" className="hover:text-white">
                  All products
                </Link>
              </li>
              <li>
                <Link href="/cart" className="hover:text-white">
                  Your cart
                </Link>
              </li>
              <li>
                <Link href="/orders" className="hover:text-white">
                  Orders
                </Link>
              </li>
            </ul>
          </nav>
          <nav aria-label="Footer account links">
            <h2 className="text-xs font-semibold uppercase tracking-caps text-accent-300">
              Account & help
            </h2>
            <ul className="mt-4 space-y-3 text-sm">
              <li>
                <Link href="/assistant" className="hover:text-white">
                  Shopping assistant
                </Link>
              </li>
              <li>
                <Link href="/auth/login" className="hover:text-white">
                  Sign in
                </Link>
              </li>
              <li>
                <Link href="/auth/register" className="hover:text-white">
                  Create account
                </Link>
              </li>
            </ul>
          </nav>
        </div>
        <div className="border-t border-white/10">
          <p className="mx-auto max-w-7xl px-4 py-5 text-xs text-ink-400 sm:px-6 lg:px-8">
            © {new Date().getFullYear()} ShopSmart AI
          </p>
        </div>
      </footer>
    </>
  );
}
