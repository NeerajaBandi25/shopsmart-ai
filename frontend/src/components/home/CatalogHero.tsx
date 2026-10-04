'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { CSSProperties, FormEvent } from 'react';
import { addCartItem, applyCartCoupon, getCart, type Cart } from '@/lib/cart-api';
import type { HeroStoryData, HomepageData } from '@/lib/api-client';
import { useCommerceStore } from '@/lib/commerce-store';
import { formatInr } from '@/lib/currency';
import styles from './CatalogHero.module.css';

const steps = [
  { label: 'Ask', progress: 0.02 },
  { label: 'Intent', progress: 0.23 },
  { label: 'Discover', progress: 0.43 },
  { label: 'Compare', progress: 0.62 },
  { label: 'Best fit', progress: 0.78 },
  { label: 'Buy', progress: 0.9 },
  { label: 'Explore', progress: 0.98 },
];

const comparisonFields = [
  { label: 'MEMORY', key: 'RAM' },
  { label: 'WEIGHT', key: 'Weight' },
  { label: 'DISPLAY', key: 'Display' },
  { label: 'GRAPHICS', key: 'Graphics' },
  { label: 'STORAGE', key: 'Storage' },
];

const sceneStops = [0, 0.16, 0.34, 0.52, 0.72, 0.86, 0.96, 1];

function sceneForProgress(progress: number): number {
  if (progress < 0.16) return 0;
  if (progress < 0.34) return 1;
  if (progress < 0.52) return 2;
  if (progress < 0.72) return 3;
  if (progress < 0.86) return 4;
  if (progress < 0.96) return 5;
  return 6;
}

function matchingOffer(promotions: HomepageData['promotions'], category: string | null) {
  return promotions.find(
    (promotion) => !promotion.scope_category || promotion.scope_category === category
  );
}

function evidenceFor(story: HeroStoryData) {
  return story.evidence.slice(0, 3).map((fact, index) => (
    <span className={styles.evidenceChip} key={`${fact.label}-${index}`}>
      <i aria-hidden="true">0{index + 1}</i>
      <b>{fact.value}</b>
      <small>{fact.label}</small>
    </span>
  ));
}

function imageForRole(product: NonNullable<HeroStoryData['candidates'][number]>, role: string) {
  return (
    product.image_gallery?.find((image) => image.role === role) ?? {
      url: product.image_url ?? '',
      alt: product.image_alt ?? product.name,
    }
  );
}

export function CatalogHero({
  story,
  promotions,
  categories,
  hasSession,
  status,
}: {
  story: HeroStoryData | null;
  promotions: HomepageData['promotions'];
  categories: HomepageData['categories'];
  hasSession: boolean;
  status: 'loading' | 'success' | 'error';
}) {
  const sectionRef = useRef<HTMLElement>(null);
  const [scene, setScene] = useState(0);
  const [cart, setCart] = useState<Cart | null>(null);
  const [cartState, setCartState] = useState<'idle' | 'adding' | 'added' | 'error'>('idle');
  const [cartMessage, setCartMessage] = useState('');
  const [coupon, setCoupon] = useState('');
  const [couponMessage, setCouponMessage] = useState('');
  const [reducedMotion, setReducedMotion] = useState(false);
  const syncCartCount = useCommerceStore((state) => state.syncCartCount);
  const products = story?.candidates ?? [];
  const selected = products.find((product) => product.id === story?.recommended_product_id);
  const displayProducts = selected
    ? [
        ...products.filter((product) => product.id !== selected.id).slice(0, 1),
        selected,
        ...products.filter((product) => product.id !== selected.id).slice(1),
      ]
    : products;
  const openingProduct = displayProducts.find((product) => product.id !== selected?.id) ?? selected;
  const openingImage = openingProduct ? imageForRole(openingProduct, 'hero') : null;
  const intentImage = openingProduct ? imageForRole(openingProduct, 'alternate') : null;
  const purchaseImage = selected ? imageForRole(selected, 'alternate') : null;
  const offer = matchingOffer(promotions, selected?.category ?? null);
  const selectedCartItem = cart?.items.find((item) => item.product_id === selected?.id);
  const selectedAlreadyAdded = Boolean(selectedCartItem?.quantity);
  const selectedAtLimit = Boolean(
    selectedCartItem && selectedCartItem.quantity >= selectedCartItem.max_purchase_quantity
  );

  useEffect(() => {
    if (!hasSession) return;
    let active = true;
    getCart()
      .then((savedCart) => {
        if (!active) return;
        setCart(savedCart);
        syncCartCount(savedCart);
        if (savedCart.coupon_code) setCoupon(savedCart.coupon_code);
        if (savedCart.coupon_evaluation) {
          const evaluation = savedCart.coupon_evaluation;
          setCouponMessage(
            evaluation.eligible
              ? `${evaluation.code || evaluation.name} applied. Your cart saved ${formatInr(evaluation.discount_cents)}.`
              : `${evaluation.code || evaluation.name} is not eligible for this cart.`
          );
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [hasSession, syncCartCount]);

  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;
    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updateMotionPreference = () => {
      setReducedMotion(motionPreference.matches);
      section.dataset.reduced = String(motionPreference.matches);
    };
    updateMotionPreference();
    motionPreference.addEventListener('change', updateMotionPreference);

    let frame = 0;
    const updateProgress = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (motionPreference.matches) return;
        const bounds = section.getBoundingClientRect();
        const travel = Math.max(1, section.offsetHeight - window.innerHeight);
        const progress = Math.min(1, Math.max(0, -bounds.top / travel));
        section.style.setProperty('--story-progress', String(progress));
        section.style.setProperty('--light-shift', `${progress * 100}%`);
        section.style.setProperty('--reveal', `${Math.min(100, Math.max(0, progress * 122))}%`);
        const nextScene = sceneForProgress(progress);
        const sceneProgress = Math.min(
          1,
          Math.max(
            0,
            (progress - sceneStops[nextScene]) /
              Math.max(0.001, sceneStops[nextScene + 1] - sceneStops[nextScene])
          )
        );
        section.style.setProperty('--scene-progress', String(sceneProgress));
        section.style.setProperty('--object-lift', `${-18 * sceneProgress}px`);
        section.style.setProperty('--object-tilt', `${6 * sceneProgress}deg`);
        section.style.setProperty('--object-scale', String(1.08 - sceneProgress * 0.12));
        section.style.setProperty('--mask-x', `${43 + sceneProgress * 10}%`);
        section.style.setProperty('--mask-y', `${42 + sceneProgress * 8}%`);
        section.style.setProperty('--intent-product-y', `${14 + sceneProgress * 7}vh`);
        section.style.setProperty('--intent-drift', `${(0.5 - sceneProgress) * 36}px`);
        section.style.setProperty('--intent-orbit-y', `${55 + (0.5 - sceneProgress) * 8}%`);
        section.style.setProperty('--candidate-left-shift', `${(sceneProgress - 0.5) * 46}px`);
        section.style.setProperty('--candidate-right-shift', `${(0.5 - sceneProgress) * 46}px`);
        section.style.setProperty('--candidate-center-lift', `${(0.5 - sceneProgress) * 22}px`);
        section.style.setProperty('--compare-left-y', `${8 - sceneProgress * 8}%`);
        section.style.setProperty('--compare-right-y', `${7 - sceneProgress * 7}%`);
        section.style.setProperty('--compare-left-tilt', `${14 - sceneProgress * 10}deg`);
        section.style.setProperty('--compare-right-tilt', `${-14 + sceneProgress * 10}deg`);
        section.style.setProperty('--compare-rail-bottom', `${18 + sceneProgress * 3}%`);
        section.style.setProperty('--recommendation-scale', String(0.9 + sceneProgress * 0.1));
        section.dataset.scene = String(nextScene);
        setScene((current) => (current === nextScene ? current : nextScene));
      });
    };
    if (!motionPreference.matches) {
      updateProgress();
      window.addEventListener('scroll', updateProgress, { passive: true });
      window.addEventListener('resize', updateProgress);
    }
    return () => {
      cancelAnimationFrame(frame);
      motionPreference.removeEventListener('change', updateMotionPreference);
      window.removeEventListener('scroll', updateProgress);
      window.removeEventListener('resize', updateProgress);
    };
  }, [story]);

  const jumpToStep = useCallback(
    (progress: number) => {
      const section = sectionRef.current;
      if (!section) return;
      const bounds = section.getBoundingClientRect();
      const pageTop = window.scrollY + bounds.top;
      const travel = Math.max(0, section.offsetHeight - window.innerHeight);
      window.scrollTo({
        top: pageTop + travel * progress,
        behavior: reducedMotion ? 'auto' : 'smooth',
      });
    },
    [reducedMotion]
  );

  async function addSelectedToCart() {
    if (!selected) return;
    setCartState('adding');
    setCartMessage('');
    setCouponMessage('');
    try {
      const result = await addCartItem(selected.id, 1);
      setCart(result);
      syncCartCount(result);
      setCartState('added');
      setCartMessage('Added. Your cart has been updated.');
    } catch (cause: unknown) {
      setCartState('error');
      setCartMessage(
        cause instanceof Error &&
          /unauthorized|sign in|log in|session (required|invalid|expired)/i.test(cause.message)
          ? 'Sign in to add this product to your cart.'
          : cause instanceof Error
            ? cause.message
            : 'The cart could not be updated.'
      );
    }
  }

  async function applyOffer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!coupon.trim()) return;
    setCouponMessage('Checking this code against your cart…');
    try {
      const result = await applyCartCoupon(coupon.trim());
      setCart(result);
      syncCartCount(result);
      const evaluation = result.coupon_evaluation;
      setCouponMessage(
        evaluation?.eligible
          ? `${evaluation.code || coupon.trim()} applied. Your cart saved ${formatInr(evaluation.discount_cents)}.`
          : 'The cart service did not approve this code for the current items.'
      );
    } catch (cause: unknown) {
      setCouponMessage(
        cause instanceof Error ? cause.message : 'The cart could not verify this offer.'
      );
    }
  }

  if (!story || !selected) {
    return (
      <section className={styles.unavailable} aria-labelledby="hero-heading">
        <p>SHOPSMART / LIVE CATALOG</p>
        <h1 id="hero-heading">A clearer way to choose.</h1>
        <p>
          {status === 'loading'
            ? 'Finding a live, in-stock shortlist…'
            : 'The guided shortlist is unavailable right now. Browse the live catalog instead.'}
        </p>
        <Link href="/products">
          Explore products <span aria-hidden="true">↗</span>
        </Link>
      </section>
    );
  }

  const comparisonValues = comparisonFields
    .map((field) => ({
      ...field,
      values: displayProducts.map((product) => String(product.specifications?.[field.key] ?? '—')),
    }))
    .filter(
      (field) => field.values.some((value) => value !== '—') && new Set(field.values).size > 1
    )
    .slice(0, 3);
  const discount = cart?.coupon_evaluation?.eligible
    ? cart.coupon_evaluation.discount_cents
    : (cart?.discount_total_cents ?? 0);
  const finalPrice = cart?.total_cents ?? selected.price;
  const cartCount = cart?.items.reduce((total, item) => total + item.quantity, 0) ?? 0;

  return (
    <section
      ref={sectionRef}
      className={styles.story}
      data-scene={scene}
      style={
        {
          '--story-progress': '0',
          '--scene-progress': '0',
          '--light-shift': '0%',
          '--reveal': '0%',
          '--object-lift': '0px',
          '--object-tilt': '0deg',
          '--object-scale': '1',
          '--mask-x': '43%',
          '--mask-y': '42%',
          '--intent-product-y': '14vh',
          '--intent-drift': '0px',
          '--intent-orbit-y': '55%',
          '--candidate-left-shift': '0px',
          '--candidate-right-shift': '0px',
          '--candidate-center-lift': '0px',
          '--compare-left-y': '8%',
          '--compare-right-y': '7%',
          '--compare-left-tilt': '14deg',
          '--compare-right-tilt': '-14deg',
          '--compare-rail-bottom': '18%',
          '--recommendation-scale': '1',
        } as CSSProperties
      }
      aria-label="ShopSmart AI shopping story"
    >
      <div className={styles.sticky}>
        <div className={styles.stage} data-scene={scene}>
          <div className={styles.ambient} aria-hidden="true">
            <div className={styles.halo} />
            <div className={styles.lightBlade} />
            <div className={styles.floorLine} />
            <div className={styles.grain} />
          </div>

          <header className={styles.topbar}>
            <Link href="/" className={styles.wordmark} aria-label="ShopSmart home">
              SHOPSMART<span>AI</span>
            </Link>
            <p>
              LIVE CATALOG <i /> DECISION ENGINE
            </p>
            <Link href="/cart" className={styles.cartLink} aria-label="View cart">
              CART <b>{cartCount}</b>
            </Link>
          </header>

          <div className={styles.storyCanvas}>
            <h1 className={styles.openingTitle} data-layer="opening" aria-hidden={scene !== 0}>
              <span>ASK BETTER.</span>
              <span>
                BUY <i>BETTER.</i>
              </span>
            </h1>
            <div className={styles.openingLabel} data-layer="opening" aria-hidden={scene !== 0}>
              <span>01 — THE QUESTION</span>
              <span>SCROLL TO SEE IT THINK</span>
            </div>

            <div className={styles.primaryObject} data-layer="primary" aria-hidden="true">
              <div className={styles.primaryMask}>
                {openingImage && (
                  <>
                    <Image
                      src={openingImage.url || '/images/products/portfolio/laptops/01.jpg'}
                      alt=""
                      fill
                      priority
                      sizes="(max-width: 700px) 96vw, 72vw"
                      className={`${styles.primaryImage} ${styles.askImage}`}
                    />
                    <Image
                      src={
                        intentImage?.url ||
                        openingImage.url ||
                        '/images/products/portfolio/laptops/01.jpg'
                      }
                      alt=""
                      fill
                      sizes="(max-width: 700px) 96vw, 72vw"
                      className={`${styles.primaryImage} ${styles.intentImage}`}
                    />
                  </>
                )}
              </div>
              <span className={styles.objectLight} />
              <span className={styles.primaryBrand}>
                {openingProduct?.brand || openingProduct?.category}
              </span>
              <span className={styles.primaryName}>{openingProduct?.name}</span>
            </div>

            <div className={styles.intentStory} data-layer="intent" aria-hidden={scene !== 1}>
              <p className={styles.eyebrow}>02 — YOUR INTENT, DECODED</p>
              <h2>{story.query}</h2>
              <div className={styles.intentOrbit} aria-label="Understood requirements">
                <span>CODING</span>
                <span>LOCAL AI</span>
                <span>16 GB+</span>
                <b>UNDER {formatInr(story.budget_minor)}</b>
              </div>
              <p className={styles.understood}>
                <i>✳</i> Request understood <span>·</span> checking real stock and specs
              </p>
            </div>

            <div className={styles.discoveryStory} data-layer="discovery" aria-hidden={scene !== 2}>
              <div className={styles.sceneHeading}>
                <span>03 / DISCOVER</span>
                <h2>Three ways forward.</h2>
              </div>
              <div className={styles.productConstellation}>
                {displayProducts.map((product, index) => (
                  <Link
                    href={`/products/${encodeURIComponent(product.id)}`}
                    className={`${styles.candidate} ${styles[`candidate${index + 1}`]}`}
                    data-selected={product.id === selected.id}
                    key={product.id}
                    tabIndex={scene === 2 ? 0 : -1}
                    aria-label={`View ${product.name}, ${formatInr(product.price)}`}
                  >
                    <span className={styles.candidateImage}>
                      <Image
                        src={product.image_url || ''}
                        alt={product.image_alt || product.name}
                        fill
                        sizes="(max-width: 700px) 58vw, 38vw"
                        loading={index === 0 ? 'eager' : 'lazy'}
                      />
                    </span>
                    <span className={styles.candidateIndex}>0{index + 1}</span>
                    <span className={styles.candidateMeta}>
                      <small>{product.brand || product.category}</small>
                      <b>{product.name}</b>
                      <i>{formatInr(product.price)}</i>
                    </span>
                  </Link>
                ))}
              </div>
              <p className={styles.sourceNote}>
                THREE IN-STOCK MATCHES <i /> FROM YOUR LIVE CATALOG
              </p>
            </div>

            <div
              className={styles.comparisonStory}
              data-layer="comparison"
              aria-hidden={scene !== 3}
            >
              <div className={styles.sceneHeading}>
                <span>04 / COMPARE</span>
                <h2>
                  Same brief.
                  <br />
                  <em>Different strengths.</em>
                </h2>
              </div>
              <div className={styles.compareObjects}>
                {displayProducts.map((product, index) => (
                  <div
                    className={`${styles.compareProduct} ${styles[`compare${index + 1}`]}`}
                    key={product.id}
                  >
                    <span className={styles.compareImage}>
                      <Image
                        src={product.image_url || ''}
                        alt=""
                        fill
                        sizes="(max-width: 700px) 34vw, 25vw"
                        loading="lazy"
                      />
                    </span>
                    <b>{product.brand || product.name}</b>
                  </div>
                ))}
              </div>
              <div
                className={styles.comparisonRail}
                aria-label="Live product specification comparison"
              >
                {comparisonValues.map((fact) => (
                  <div className={styles.specRail} key={fact.key}>
                    <span className={styles.specLabel}>{fact.label}</span>
                    {fact.values.map((value, valueIndex) => (
                      <b
                        className={
                          displayProducts[valueIndex].id === selected.id ? styles.specChosen : ''
                        }
                        key={`${fact.key}-${displayProducts[valueIndex].id}`}
                      >
                        {value}
                        <i aria-hidden="true" />
                      </b>
                    ))}
                  </div>
                ))}
                <div className={`${styles.specRail} ${styles.priceRail}`}>
                  <span className={styles.specLabel}>PRICE</span>
                  {displayProducts.map((product) => (
                    <b
                      className={product.id === selected.id ? styles.specChosen : ''}
                      key={product.id}
                    >
                      {formatInr(product.price)}
                      <i aria-hidden="true" />
                    </b>
                  ))}
                </div>
              </div>
              <p className={styles.sourceNote}>
                PUBLISHED PRODUCT SPECS <i /> DIFFERENCES, MADE VISIBLE
              </p>
            </div>

            <div
              className={styles.recommendationStory}
              data-layer="recommendation"
              aria-hidden={scene !== 4}
            >
              <p className={styles.eyebrow}>05 — SHOPSMART ANALYSIS</p>
              <div className={styles.recommendationObject}>
                {products
                  .filter((product) => product.id !== selected.id)
                  .map((product, index) => (
                    <span
                      className={`${styles.recedingObject} ${styles[`receding${index + 1}`]}`}
                      key={product.id}
                    >
                      <Image
                        src={product.image_url || ''}
                        alt=""
                        fill
                        sizes="16vw"
                        loading="lazy"
                      />
                    </span>
                  ))}
                <span className={styles.recommendationImage}>
                  <Image
                    src={selected.image_url || ''}
                    alt=""
                    fill
                    sizes="(max-width: 700px) 92vw, 62vw"
                    loading="lazy"
                  />
                </span>
                <span className={styles.bestFit}>
                  BEST
                  <br />
                  <b>FIT</b>
                </span>
              </div>
              <div className={styles.recommendationCopy}>
                <h2>{selected.name}</h2>
                <p>{story.recommendation}</p>
                <div className={styles.evidence}>{evidenceFor(story)}</div>
                <div className={styles.recommendationPrice}>
                  <b>{formatInr(selected.price)}</b>
                  <span>{formatInr(story.savings_minor)} below your budget</span>
                </div>
              </div>
            </div>

            <div className={styles.commerceStory} data-layer="commerce" aria-hidden={scene !== 5}>
              <p className={styles.eyebrow}>06 — WHEN YOU’RE READY</p>
              <div className={styles.commerceProduct}>
                <div className={styles.commerceProductImage}>
                  <Image
                    src={purchaseImage?.url || selected.image_url || ''}
                    alt=""
                    fill
                    sizes="(max-width: 700px) 88vw, 58vw"
                    loading="lazy"
                  />
                </div>
                <p>
                  {selected.brand || selected.category}
                  <span>·</span>
                  {selected.stock_quantity} IN STOCK
                </p>
                <h2>{selected.name}</h2>
                <b className={styles.commercePrice}>{formatInr(selected.price)}</b>
                <button
                  className={styles.addButton}
                  type="button"
                  onClick={addSelectedToCart}
                  disabled={
                    cartState === 'adding' || selected.stock_quantity < 1 || selectedAtLimit
                  }
                >
                  {cartState === 'adding'
                    ? 'ADDING…'
                    : cartState === 'added' || selectedAlreadyAdded
                      ? 'ADDED TO CART ✓'
                      : 'ADD TO CART'}
                  <span aria-hidden="true">↗</span>
                </button>
                {cartState === 'error' && /sign in/i.test(cartMessage) && (
                  <Link className={styles.signInLink} href="/auth/login">
                    Sign in to continue
                  </Link>
                )}
                <p className={styles.cartMessage} role="status" aria-live="polite">
                  {cartMessage || (selectedAlreadyAdded ? 'This product is in your cart.' : '')}
                </p>
              </div>
              <div
                className={styles.cartOrbit}
                data-arrived={cartState === 'added'}
                aria-live="polite"
              >
                <span>YOUR CART</span>
                <b>{cartCount}</b>
                {cartState === 'added' && <i>✓</i>}
              </div>
              <span
                className={styles.cartFlight}
                data-flying={cartState === 'added'}
                aria-hidden="true"
              >
                <Image src={selected.image_url || ''} alt="" fill sizes="100px" />
              </span>
              {offer && (
                <div className={styles.offerStory}>
                  <span>LIVE CATALOG OFFER · VERIFIED IN CART</span>
                  <b>{offer.name}</b>
                  <small>
                    {offer.discount_type === 'percentage'
                      ? `${offer.discount_value}% off eligible items`
                      : `${formatInr(offer.discount_value)} off eligible items`}
                  </small>
                  {(cartState === 'added' || selectedAlreadyAdded) && (
                    <form onSubmit={applyOffer}>
                      <label className="sr-only" htmlFor="hero-offer-code">
                        Promotion code
                      </label>
                      <input
                        id="hero-offer-code"
                        value={coupon}
                        onChange={(event) => setCoupon(event.target.value)}
                        placeholder="Promotion code"
                        autoComplete="off"
                      />
                      <button type="submit" disabled={!coupon.trim()}>
                        APPLY
                      </button>
                    </form>
                  )}
                  {couponMessage && <small role="status">{couponMessage}</small>}
                  {discount > 0 && (
                    <strong>
                      CART VERIFIED · −{formatInr(discount)} · {formatInr(finalPrice)} TOTAL
                    </strong>
                  )}
                </div>
              )}
              <Link
                className={styles.pdpLink}
                href={`/products/${encodeURIComponent(selected.id)}`}
              >
                PRODUCT DETAILS <span>↗</span>
              </Link>
            </div>

            <div className={styles.releaseStory} data-layer="release" aria-hidden={scene !== 6}>
              <p className={styles.eyebrow}>07 — DECIDE, THEN EXPLORE</p>
              <h2>
                Now the catalog
                <br />
                <em>opens up.</em>
              </h2>
              <Link
                className={styles.releaseProduct}
                href={`/products/${encodeURIComponent(selected.id)}`}
              >
                <span className={styles.releaseImage}>
                  <Image src={selected.image_url || ''} alt="" fill sizes="28vw" loading="lazy" />
                </span>
                <span>
                  <small>YOUR BEST FIT · LIVE CATALOG</small>
                  <b>{selected.name}</b>
                  <i>
                    {formatInr(selected.price)} <em>VIEW PRODUCT ↗</em>
                  </i>
                </span>
              </Link>
              <nav aria-label="Explore catalog categories">
                {categories.slice(0, 3).map((category, index) => (
                  <Link
                    href={`/products?category=${encodeURIComponent(category.value)}`}
                    key={category.value}
                  >
                    <i>0{index + 1}</i>
                    <b>{category.label}</b>
                    <small>{category.count} products</small>
                  </Link>
                ))}
              </nav>
            </div>
          </div>

          <nav className={styles.progressNav} aria-label="Shopping story progress">
            <div className={styles.progressTrack}>
              <i />
            </div>
            {steps.map((step, index) => (
              <button
                type="button"
                key={step.label}
                aria-label={`Go to ${step.label} scene`}
                aria-current={scene === index ? 'step' : undefined}
                onClick={() => jumpToStep(step.progress)}
              >
                <i>0{index + 1}</i>
                <span>{step.label}</span>
              </button>
            ))}
          </nav>
        </div>
      </div>

      <div className={styles.reducedStory} data-reduced-story="true">
        <p className={styles.eyebrow}>SHOPSMART · LIVE CATALOG</p>
        <h2>ASK BETTER. BUY BETTER.</h2>
        <p className={styles.reducedQuery}>{story.query}</p>
        <div className={styles.reducedCandidates}>
          {displayProducts.map((product) => (
            <article key={product.id} data-recommended={product.id === selected.id}>
              <Image
                src={product.image_url || ''}
                alt={product.image_alt || product.name}
                width={360}
                height={360}
              />
              <span>{product.brand || product.category}</span>
              <h3>{product.name}</h3>
              <b>{formatInr(product.price)}</b>
              {product.id === selected.id && <p>BEST FIT · {story.recommendation}</p>}
            </article>
          ))}
        </div>
        <div className={styles.reducedFacts}>{evidenceFor(story)}</div>
        <button
          className={styles.addButton}
          type="button"
          onClick={addSelectedToCart}
          disabled={cartState === 'adding' || selected.stock_quantity < 1 || selectedAtLimit}
        >
          {cartState === 'added' || selectedAlreadyAdded
            ? 'ADDED TO CART ✓'
            : cartState === 'adding'
              ? 'ADDING…'
              : 'ADD TO CART'}
        </button>
        <p role="status">
          {cartMessage || (selectedAlreadyAdded ? 'This product is in your cart.' : '')}
        </p>
      </div>
    </section>
  );
}
