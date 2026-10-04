'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { AddToCartButton } from '@/components/AddToCartButton';
import { CategoryCard } from '@/components/CategoryCard';
import { formatInr } from '@/lib/currency';
import {
  getHomepage,
  getHeroStory,
  type HomepageData,
  type HeroStoryData,
  type Product,
} from '@/lib/api-client';
import { CatalogHero } from './CatalogHero';
import styles from './HomeMerchandise.module.css';

function ProductTile({ product }: { product: Product }) {
  const hasDiscount = product.list_price !== null && product.list_price > product.price;

  return (
    <article
      className={`${styles.productTile} flex min-w-0 flex-col rounded-2xl border border-sand-200 bg-white p-3 shadow-tile transition-shadow duration-300 hover:shadow-tile-hover`}
    >
      <Link
        href={`/products/${encodeURIComponent(product.id)}`}
        aria-label={`View ${product.name} details`}
        className="group relative mb-4 block aspect-[4/3] overflow-hidden rounded-xl bg-sand-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
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

export function HomePageExperience({ hasSession = false }: { hasSession?: boolean }) {
  const [merchandise, setMerchandise] = useState<HomepageData | null>(null);
  const [heroStory, setHeroStory] = useState<HeroStoryData | null>(null);
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    setStatus('loading');

    Promise.all([getHomepage(), getHeroStory().catch(() => null)])
      .then(([page, story]) => {
        if (active) {
          setMerchandise(page);
          setHeroStory(story);
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

  const featuredProducts = (merchandise?.featured || [])
    .filter((product) => product.stock_quantity > 0)
    .slice(0, 8);
  const discoveryProducts = (merchandise?.trending || [])
    .filter((product) => product.stock_quantity > 0)
    .slice(0, 4);
  const products = Array.from(
    new Map(
      [...featuredProducts, ...discoveryProducts].map((product) => [product.id, product])
    ).values()
  );
  const recommendations = (merchandise?.recommendations || [])
    .filter((product) => product.stock_quantity > 0)
    .slice(0, 4);
  const deals = products.filter(
    (product) =>
      product.stock_quantity > 0 &&
      product.list_price !== null &&
      product.list_price > product.price
  );

  return (
    <>
      <main>
        <CatalogHero
          story={heroStory}
          promotions={merchandise?.promotions || []}
          categories={merchandise?.categories || []}
          hasSession={hasSession}
          status={status}
        />

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
              className="mt-7 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
            >
              {(merchandise?.categories || []).map((category, index) =>
                category.image_url ? (
                  <CategoryCard
                    key={category.value}
                    numeral={String(index + 1).padStart(2, '0')}
                    name={category.label}
                    href={`/products?category=${encodeURIComponent(category.value)}`}
                    image={category.image_url}
                    alt={category.image_alt || `${category.label} from the product catalog`}
                    badge={`${category.count} listings`}
                  />
                ) : (
                  <Link
                    key={category.value}
                    href={`/products?category=${encodeURIComponent(category.value)}`}
                    className="group flex min-h-24 items-center gap-3 border-t border-sand-200 py-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                  >
                    <span aria-hidden="true" className="font-display text-2xl text-accent-700">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <span>
                      <span className="block text-sm font-semibold text-ink-900 group-hover:text-accent-700">
                        {category.label}
                      </span>
                      <span className="mt-1 block text-xs text-ink-500">
                        {category.count} listings
                      </span>
                    </span>
                  </Link>
                )
              )}
            </nav>
          </div>
        </section>

        <section aria-labelledby="featured-heading" className="bg-blush-50">
          <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-caps text-accent-700">
                  A considered selection
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
              <div
                className={`${styles.shelf} mt-8 grid grid-cols-2 gap-x-3 gap-y-4 sm:gap-x-5 sm:gap-y-8 lg:grid-cols-4`}
              >
                {featuredProducts.map((product) => (
                  <ProductTile key={product.id} product={product} />
                ))}
              </div>
            )}
          </div>
        </section>

        {status === 'success' && discoveryProducts.length > 0 && (
          <section aria-labelledby="discovery-heading" className="bg-sand-100">
            <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
              <p className="text-xs font-semibold uppercase tracking-caps text-accent-700">
                Keep exploring
              </p>
              <h2
                id="discovery-heading"
                className="mt-2 font-display text-3xl font-bold text-ink-900"
              >
                Worth a closer look
              </h2>
              <div
                className={`${styles.shelf} mt-8 grid grid-cols-2 gap-x-3 gap-y-4 sm:gap-x-5 sm:gap-y-8 lg:grid-cols-4`}
              >
                {discoveryProducts.map((product) => (
                  <ProductTile key={product.id} product={product} />
                ))}
              </div>
            </div>
          </section>
        )}

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
              <div
                className={`${styles.shelf} mt-8 grid grid-cols-2 gap-x-3 gap-y-4 sm:gap-x-5 sm:gap-y-8 lg:grid-cols-4`}
              >
                {deals.slice(0, 4).map((product) => (
                  <ProductTile key={product.id} product={product} />
                ))}
              </div>
            </div>
          </section>
        )}

        {status === 'success' && recommendations.length > 0 && (
          <section aria-labelledby="recommendations-heading" className="bg-blush-50">
            <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
              <p className="text-xs font-semibold uppercase tracking-caps text-accent-700">
                Something to explore
              </p>
              <h2
                id="recommendations-heading"
                className="mt-2 font-display text-3xl font-bold text-ink-900"
              >
                Your next discovery
              </h2>
              <p className="mt-3 text-sm text-ink-500">
                Explore more of the catalog, or ask the assistant for a shortlist around your needs.
              </p>
              <div
                className={`${styles.shelf} mt-8 grid grid-cols-2 gap-x-3 gap-y-4 sm:gap-x-5 sm:gap-y-8 lg:grid-cols-4`}
              >
                {recommendations.map((product) => (
                  <ProductTile key={product.id} product={product} />
                ))}
              </div>
            </div>
          </section>
        )}

        {status === 'success' && !!merchandise?.promotions.length && (
          <section aria-labelledby="promotions-heading" className="bg-leaf-800 text-white">
            <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
              <p className="text-xs font-semibold uppercase tracking-caps text-clay-200">
                Current promotions
              </p>
              <h2 id="promotions-heading" className="mt-2 font-display text-3xl font-bold">
                A little extra possibility
              </h2>
              <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {merchandise.promotions.map((promotion) => (
                  <article key={promotion.name} className="rounded-xl border border-white/20 p-5">
                    <h3 className="font-display text-xl">{promotion.name}</h3>
                    <p className="mt-3 text-lg text-clay-200">
                      {promotion.discount_type === 'percentage'
                        ? promotion.discount_value + '% off eligible items'
                        : formatInr(promotion.discount_value) + ' off eligible items'}
                    </p>
                    {promotion.description && (
                      <p className="mt-2 text-sm leading-relaxed text-white/80">
                        {promotion.description}
                      </p>
                    )}
                    <p className="mt-3 text-xs text-white/70">
                      Eligibility and final savings are checked at checkout.
                    </p>
                    <Link
                      href={
                        promotion.scope_category
                          ? '/products?category=' + encodeURIComponent(promotion.scope_category)
                          : '/products'
                      }
                      className="mt-4 inline-flex min-h-11 items-center text-sm underline underline-offset-4"
                    >
                      Explore the catalog →
                    </Link>
                  </article>
                ))}
              </div>
            </div>
          </section>
        )}

        <section aria-labelledby="shopping-details-heading" className="bg-leaf-800 text-white">
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
