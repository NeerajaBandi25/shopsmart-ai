'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { AddToCartButton } from '@/components/AddToCartButton';
import type { Product } from '@/lib/api-client';
import { formatInr } from '@/lib/currency';
import styles from './CatalogHero.module.css';

const story = [
  {
    label: 'Discover',
    title: 'Your next buy, understood.',
    kicker: 'A more considered way to shop.',
  },
  {
    label: 'Your brief',
    title: 'Start with what matters.',
    kicker: 'Tell the assistant what you need.',
  },
  {
    label: 'Explore',
    title: 'Real options. Side by side.',
    kicker: 'A shortlist from the live catalog.',
  },
  {
    label: 'Compare',
    title: 'See the differences clearly.',
    kicker: 'Compare published details and prices.',
  },
  {
    label: 'Decide',
    title: 'Find your kind of fit.',
    kicker: 'Ask for a recommendation grounded in your brief.',
  },
  {
    label: 'Purchase',
    title: 'When you are ready.',
    kicker: 'Add a real catalog item to your cart.',
  },
];

type Fact = { label: string; value: string };
const DEFAULT_BRIEF = 'Find laptops under \u20b970,000';

function readIntent(query: string) {
  const lower = query.toLowerCase();
  const signals = [
    { terms: ['laptop', 'notebook'], category: 'laptops', label: 'Laptops' },
    { terms: ['phone', 'mobile'], category: 'smartphones', label: 'Smartphones' },
    { terms: ['headphone', 'earbud'], category: 'headphones', label: 'Headphones' },
    { terms: ['camera'], category: 'cameras', label: 'Cameras' },
    { terms: ['watch', 'wearable'], category: 'smartwatches', label: 'Smartwatches' },
    { terms: ['tablet'], category: 'tablets', label: 'Tablets' },
    { terms: ['television', ' tv'], category: 'televisions', label: 'Televisions' },
    { terms: ['gaming', 'controller', 'console'], category: 'gaming', label: 'Gaming' },
    { terms: ['shoe', 'footwear', 'sneaker', 'boot'], category: 'footwear', label: 'Footwear' },
    { terms: ['fashion', 'clothing', 'dress', 'jean'], category: 'fashion', label: 'Fashion' },
  ];
  const category = signals.find((signal) => signal.terms.some((term) => lower.includes(term)));
  const tail = lower.split('under')[1];
  const token = tail?.replace(/[^0-9,k.]/g, '').trim() || '';
  const amount = token.match(/[0-9,.]+/)?.[0];
  const raw = amount ? Number(amount.replace(/,/g, '')) : null;
  const budgetInr =
    raw === null ? null : raw * (token.endsWith('k') || tail?.includes('thousand') ? 1000 : 1);
  return {
    category: category?.category ?? null,
    categoryLabel: category?.label ?? 'All departments',
    budgetInr,
  };
}

function facts(product: Product): Fact[] {
  const specs = product.specifications || {};
  return Object.entries(specs)
    .filter(([key, value]) => !key.startsWith('_') && typeof value !== 'boolean' && value !== null)
    .slice(0, 2)
    .map(([label, value]) => ({ label: label.replace(/[_-]/g, ' '), value: String(value) }));
}

export function CatalogHero({
  products,
  status,
}: {
  products: Product[];
  status: 'loading' | 'success' | 'error';
}) {
  const [scene, setScene] = useState(0);
  const [brief, setBrief] = useState(DEFAULT_BRIEF);
  const intent = readIntent(brief);
  const candidates = useMemo(
    () =>
      products
        .filter(
          (p) =>
            p.stock_quantity > 0 &&
            (!intent.category || p.category === intent.category) &&
            (intent.budgetInr === null || p.price <= intent.budgetInr * 100)
        )
        .slice(0, 3),
    [intent.budgetInr, intent.category, products]
  );
  const comparisonFacts = ['RAM', 'Graphics', 'Storage', 'Display'].filter((key) =>
    candidates.some((product) =>
      Object.prototype.hasOwnProperty.call(product.specifications || {}, key)
    )
  );
  const featured =
    candidates[0] ||
    products.find((p) => p.stock_quantity > 0 && p.category === 'laptops') ||
    products[0];
  const budgetDisplay =
    intent.budgetInr === null
      ? 'No limit stated'
      : formatInr(intent.budgetInr * 100).replace(/\.00$/, '');
  const priceLeader = candidates.reduce<Product | undefined>(
    (best, item) => (!best || item.price < best.price ? item : best),
    undefined
  );

  return (
    <section className={styles.hero} aria-labelledby="hero-heading">
      <div className={styles.ambient} aria-hidden="true" />
      <div className={styles.shell}>
        <div className={styles.topline}>
          <span>
            <i aria-hidden="true" /> SHOPSMART INTELLIGENCE
          </span>
          <span>01 — 06&nbsp;&nbsp; / &nbsp;&nbsp;A clearer way to choose</span>
        </div>

        <div className={styles.stage}>
          <div className={styles.editorial} key={`copy-${scene}`}>
            <p className={styles.kicker}>{story[scene].kicker}</p>
            <h1 id="hero-heading" aria-live="polite">
              {scene === 0 ? (
                <>
                  Your next buy,
                  <br />
                  <em>understood.</em>
                </>
              ) : (
                story[scene].title
              )}
            </h1>
            {scene === 0 && (
              <p className={styles.intro}>
                Discover, compare and understand the details—then shop from the products in our
                catalog.
              </p>
            )}

            {scene === 1 && (
              <div className={styles.brief}>
                <span className={styles.briefMark} aria-hidden="true">
                  ✳
                </span>
                <div>
                  <span>YOUR SHOPPING BRIEF</span>
                  <form action="/assistant" method="get" className={styles.briefForm}>
                    <label className="sr-only" htmlFor="hero-shopping-brief">
                      What would you like to find?
                    </label>
                    <input
                      id="hero-shopping-brief"
                      type="search"
                      name="q"
                      value={brief}
                      onChange={(event) => setBrief(event.target.value)}
                    />
                    <button type="submit" aria-label="Ask the shopping assistant">
                      ↗
                    </button>
                  </form>
                  <small>Need · category · budget</small>
                </div>
              </div>
            )}

            {scene === 4 && (
              <div className={styles.recommendation}>
                <span className={styles.recommendationLabel}>A STARTING POINT</span>
                {priceLeader ? (
                  <>
                    <strong>{priceLeader.name}</strong>
                    <p>Lowest listed price among these in-stock options.</p>
                    <div className={styles.evidence}>
                      <span>
                        Catalog price <b>{formatInr(priceLeader.price)}</b>
                      </span>
                      <span>
                        Availability <b>In stock</b>
                      </span>
                    </div>
                    <Link href={`/assistant?q=${encodeURIComponent(brief)}`}>
                      Ask AI to rank for your needs <span aria-hidden="true">↗</span>
                    </Link>
                  </>
                ) : (
                  <p>
                    Explore available products and ask the assistant for a fit based on your needs.
                  </p>
                )}
              </div>
            )}

            {(scene === 0 || scene === 1 || scene === 4) && (
              <div className={styles.ctas}>
                {scene === 1 ? (
                  <Link
                    href={`/assistant?q=${encodeURIComponent(brief)}`}
                    className={styles.primary}
                  >
                    Explore this brief <span aria-hidden="true">↗</span>
                  </Link>
                ) : (
                  <button
                    type="button"
                    className={styles.primary}
                    onClick={() => setScene(scene + 1)}
                  >
                    Follow the decision <span aria-hidden="true">↓</span>
                  </button>
                )}
                {scene === 0 ? (
                  <Link href="/assistant" className={styles.secondary}>
                    Ask the shopping assistant <span aria-hidden="true">↗</span>
                  </Link>
                ) : (
                  <Link href="/products" className={styles.secondary}>
                    Browse all products <span aria-hidden="true">↗</span>
                  </Link>
                )}
              </div>
            )}

            {scene === 5 && (
              <div className={styles.purchase}>
                {featured && (
                  <>
                    <div className={styles.purchaseItem}>
                      <span>SELECTED FROM THE LIVE CATALOG</span>
                      <strong>{featured.name}</strong>
                      <b>{formatInr(featured.price)}</b>
                    </div>
                    <AddToCartButton
                      productId={featured.id}
                      stockQuantity={featured.stock_quantity}
                      maxPurchaseQuantity={featured.max_purchase_quantity}
                    />
                  </>
                )}
                <Link href="/products">
                  Continue exploring the catalog <span aria-hidden="true">↗</span>
                </Link>
              </div>
            )}

            <div className={styles.sceneNav} aria-label="Hero story scenes">
              <span>THE JOURNEY</span>
              <div>
                {story.map((item, index) => (
                  <button
                    key={item.label}
                    type="button"
                    aria-label={`Scene ${index + 1}: ${item.label}`}
                    aria-current={scene === index ? 'step' : undefined}
                    onClick={() => setScene(index)}
                  >
                    <i>{String(index + 1).padStart(2, '0')}</i>
                    <span>{item.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className={styles.visual}>
            <div className={styles.visualMeta}>
              <span>LIVE CATALOG</span>
              <span>
                {scene === 2
                  ? '01 / SHORTLIST'
                  : scene === 3
                    ? '02 / DETAIL VIEW'
                    : scene === 5
                      ? '03 / YOUR CART'
                      : 'A SHOPPING STORY'}
              </span>
            </div>
            <div
              className={`${styles.productStage} ${styles[`scene${scene}`] || ''}`}
              key={`visual-${scene}`}
            >
              {featured?.image_url ? (
                <Image
                  className={styles.heroImage}
                  src={featured.image_url}
                  alt={featured.image_alt || featured.name}
                  fill
                  priority
                  sizes="(min-width: 1024px) 54vw, 96vw"
                />
              ) : (
                <div className={styles.imageFallback}>
                  {status === 'loading'
                    ? 'Finding a product from the catalog…'
                    : 'Explore the current catalog'}
                </div>
              )}
              <div className={styles.imageShade} />
              {scene === 0 && (
                <div className={styles.openingNote}>
                  <span>01</span>
                  <span>A choice, made clearer.</span>
                </div>
              )}
              {scene === 1 && (
                <div className={styles.intentOverlay}>
                  <span>✳ &nbsp; INTENT RECOGNIZED</span>
                  <p>
                    Product type <b>{intent.categoryLabel}</b>
                  </p>
                  <p>
                    Budget <b>{budgetDisplay}</b>
                  </p>
                  <p>
                    Available choices <b>{candidates.length}</b>
                  </p>
                </div>
              )}
              {(scene === 2 || scene === 3) && (
                <div className={styles.candidates}>
                  <div className={styles.candidateHeading}>
                    <span>SHORTLISTED FROM AVAILABLE PRODUCTS</span>
                    <b>{candidates.length.toString().padStart(2, '0')} OPTIONS</b>
                  </div>
                  {candidates.map((product, index) => (
                    <article className={styles.candidate} key={product.id}>
                      {product.image_url && (
                        <Image src={product.image_url} alt="" width={70} height={70} sizes="70px" />
                      )}
                      <span className={styles.rank}>0{index + 1}</span>
                      <div className={styles.candidateInfo}>
                        <b>{product.brand || product.category || 'Catalog pick'}</b>
                        <Link href={`/products/${encodeURIComponent(product.id)}`}>
                          {product.name}
                        </Link>
                        <span>
                          {facts(product)
                            .map((f) => `${f.label}: ${f.value}`)
                            .join(' · ') || `${product.stock_quantity} in stock`}
                        </span>
                      </div>
                      <strong>{formatInr(product.price)}</strong>
                    </article>
                  ))}
                  {candidates.length === 0 && (
                    <p className={styles.empty}>
                      {status === 'error'
                        ? 'The catalog is taking a moment to respond.'
                        : 'More catalog options are on their way.'}
                    </p>
                  )}
                </div>
              )}
              {scene === 4 && (
                <div className={styles.pricePanel}>
                  <span>PRICE-LED PICK FROM THIS SET</span>
                  <b>{priceLeader?.name || 'Explore the catalog'}</b>
                  <strong>{priceLeader ? formatInr(priceLeader.price) : '—'}</strong>
                  <p>Grounded in the current catalog</p>
                </div>
              )}
              {scene === 5 && (
                <div className={styles.cartStamp}>
                  <span>READY WHEN YOU ARE</span>
                  <b>
                    From discovery
                    <br />
                    to decision.
                  </b>
                  <i aria-hidden="true">↗</i>
                </div>
              )}
              {featured && (
                <div className={styles.imageCaption}>
                  <span>{featured.brand || 'SHOPSMART EDIT'}</span>
                  <b>{featured.name}</b>
                </div>
              )}
            </div>
            {scene === 3 && (
              <div
                className={styles.comparison}
                role="region"
                aria-label="Published product comparison"
              >
                <div className={styles.compareRow}>
                  <span>LISTED PRICE</span>
                  {candidates.map((p) => (
                    <b key={p.id}>{formatInr(p.price)}</b>
                  ))}
                </div>
                {comparisonFacts.map((fact) => (
                  <div className={styles.compareRow} key={fact}>
                    <span>{fact}</span>
                    {candidates.map((p) => (
                      <b key={p.id}>{String(p.specifications?.[fact] ?? 'Not listed')}</b>
                    ))}
                  </div>
                ))}
              </div>
            )}
            <div className={styles.visualFoot}>
              <span>PRODUCT DETAILS FROM THE LIVE CATALOG</span>
              <span>DISCOVER&nbsp; · &nbsp;COMPARE&nbsp; · &nbsp;DECIDE</span>
            </div>
          </div>
        </div>
        <div className={styles.progress} aria-hidden="true">
          <i style={{ width: `${((scene + 1) / story.length) * 100}%` }} />
        </div>
        <div className={styles.bottom}>
          <span>SHOP WITH MORE CONTEXT.</span>
          <span>
            Thoughtful choices begin with your priorities. <span aria-hidden="true">↘</span>
          </span>
        </div>
      </div>
    </section>
  );
}
