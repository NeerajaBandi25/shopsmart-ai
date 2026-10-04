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
  { label: 'Ask', progress: 0.025 },
  { label: 'Understand', progress: 0.19 },
  { label: 'Discover', progress: 0.37 },
  { label: 'Compare', progress: 0.55 },
  { label: 'Decide', progress: 0.73 },
  { label: 'Buy', progress: 0.9 },
];

const sceneHeadlines = [
  ['BUY WITH', 'CLARITY.'],
  ['START WITH', 'WHAT MATTERS.'],
  ['THREE WAYS', 'FORWARD.'],
  ['SEE WHAT', 'SETS THEM APART.'],
  ['ONE CLEAR', 'BEST FIT.'],
  ['MAKE THE', 'CALL YOURS.'],
];

const comparisonFields = [
  { label: 'MEMORY', key: 'RAM' },
  { label: 'WEIGHT', key: 'Weight' },
  { label: 'DISPLAY', key: 'Display' },
  { label: 'PROCESSOR', key: 'Processor' },
  { label: 'GRAPHICS', key: 'Graphics' },
  { label: 'STORAGE', key: 'Storage' },
];

function sceneForProgress(progress: number): number {
  if (progress < 0.16) return 0;
  if (progress < 0.34) return 1;
  if (progress < 0.52) return 2;
  if (progress < 0.7) return 3;
  if (progress < 0.87) return 4;
  return 5;
}

function matchingOffer(promotions: HomepageData['promotions'], category: string | null) {
  return promotions.find(
    (promotion) => !promotion.scope_category || promotion.scope_category === category
  );
}

function evidenceFor(story: HeroStoryData) {
  return story.evidence.map((fact) => (
    <span className={styles.evidenceChip} key={fact.label}>
      <i aria-hidden="true" />
      <span>{fact.label}</span>
      <b>{fact.value}</b>
    </span>
  ));
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
  const offer = matchingOffer(promotions, selected?.category ?? 'laptops');
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
    const updateMotionPreference = () => setReducedMotion(motionPreference.matches);
    updateMotionPreference();
    motionPreference.addEventListener('change', updateMotionPreference);

    let frame = 0;
    const updateProgress = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (!section || motionPreference.matches) return;
        const bounds = section.getBoundingClientRect();
        const travel = Math.max(1, section.offsetHeight - window.innerHeight);
        const progress = Math.min(1, Math.max(0, -bounds.top / travel));
        section.style.setProperty('--story-progress', String(progress));
        section.style.setProperty('--scene-drift', `${progress * 46}px`);
        section.style.setProperty('--glow-scale', String(1 + progress * 0.08));
        section.style.setProperty('--progress-width', `${progress * 100}%`);
        section.style.setProperty('--hero-scale', String(1.1 - progress * 0.48));
        const release = Math.min(1, Math.max(0, (progress - 0.94) / 0.06));
        section.style.setProperty('--light-reveal', String(release));
        section.style.setProperty('--release-wipe', `${(1 - release) * 100}%`);
        section.dataset.release = String(progress >= 0.965);
        const nextScene = sceneForProgress(progress);
        section.dataset.scene = String(nextScene);
        setScene((current) => (current === nextScene ? current : nextScene));
      });
    };

    if (!motionPreference.matches) {
      updateProgress();
      window.addEventListener('scroll', updateProgress, { passive: true });
      window.addEventListener('resize', updateProgress);
    } else {
      section.dataset.scene = '0';
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
        <p className={styles.overline}>SHOPSMART INTELLIGENCE</p>
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
      values: products.map((product) =>
        String(product.specifications?.[field.key] ?? 'Not listed')
      ),
    }))
    .filter(
      (field) =>
        field.values.some((value) => value !== 'Not listed') && new Set(field.values).size > 1
    );
  comparisonValues.push({
    label: 'PRICE',
    key: 'price',
    values: products.map((product) => formatInr(product.price)),
  });
  const visibleComparisonValues = [
    ...comparisonValues.filter((fact) => fact.key !== 'price').slice(0, 3),
    comparisonValues[comparisonValues.length - 1],
  ];
  const displayCopy = sceneHeadlines[scene];
  const discount = cart?.coupon_evaluation?.eligible
    ? cart.coupon_evaluation.discount_cents
    : (cart?.discount_total_cents ?? 0);
  const finalPrice = cart?.total_cents ?? selected.price;
  const hasVerifiedOffer = discount > 0;

  return (
    <section
      ref={sectionRef}
      className={styles.story}
      data-scene={scene}
      style={
        {
          '--story-progress': '0',
          '--scene-drift': '0px',
          '--hero-scale': '1.1',
          '--glow-scale': '1',
          '--progress-width': '0%',
          '--light-reveal': '0',
        } as CSSProperties
      }
      aria-label="ShopSmart guided shopping story"
    >
      <div className={styles.sticky}>
        <div className={styles.environment} aria-hidden="true">
          <div className={styles.environmentGlow} />
          <div className={styles.environmentFloor} />
          <div className={styles.environmentGrain} />
        </div>

        <div className={styles.topline}>
          <Link href="/" className={styles.wordmark} aria-label="ShopSmart home">
            SHOPSMART <i>AI</i>
          </Link>
          <span className={styles.edition}>A LIVE CATALOG, MADE LEGIBLE</span>
          <Link href="/cart" className={styles.cartIndicator} aria-label="View cart">
            <span className={styles.cartGlyph} aria-hidden="true">
              ↗
            </span>
            <span>CART</span>
            <b>{cart?.items.reduce((total, item) => total + item.quantity, 0) ?? 0}</b>
          </Link>
        </div>

        <div className={styles.sceneCanvas} data-scene={scene}>
          <div className={styles.copyLayer} aria-hidden="true">
            {sceneHeadlines.map((headline, index) => (
              <div className={styles.headlineScene} data-headline={index} key={headline[0]}>
                <span>{headline[0]}</span>
                <em>{headline[1]}</em>
              </div>
            ))}
          </div>
          <h1 className={styles.srOnly} aria-live="polite">
            {displayCopy.join(' ')}
          </h1>

          <div className={styles.introMeta} data-visible={scene === 0}>
            <span className={styles.liveDot} />
            <span>ASK → DISCOVER → DECIDE</span>
            <p>Your priorities in. A reasoned choice out.</p>
          </div>

          <figure className={styles.heroObject} data-visible={scene < 2} aria-hidden="true">
            <div className={styles.heroImageMask}>
              <Image
                src={selected.image_url || '/images/products/portfolio/laptops/01.jpg'}
                alt=""
                fill
                priority
                sizes="(max-width: 700px) 74vw, 48vw"
                className={styles.heroImage}
              />
            </div>
            <figcaption>
              <span>{selected.brand || selected.category}</span>
              <b>{selected.name}</b>
            </figcaption>
          </figure>

          <div
            className={styles.intentScene}
            data-story-view="intent"
            data-visible={scene === 1}
            aria-hidden={scene !== 1}
          >
            <span className={styles.sceneIndex}>01 / THE BRIEF</span>
            <p className={styles.queryText}>
              <span>Find me a</span> <b>laptop</b> <span>for</span> <b>React development</b>{' '}
              <span>and</span> <b>local AI</b>
            </p>
            <div className={styles.intentTokens}>
              <span>16 GB+ memory</span>
              <span>IN STOCK</span>
              <span>UNDER {formatInr(story.budget_minor)}</span>
            </div>
            <p className={styles.recognition}>
              <i aria-hidden="true">✳</i> Intent understood <span>·</span> budget and availability
              checked against the catalog
            </p>
          </div>

          <div
            className={styles.candidateScene}
            data-story-view="candidates"
            data-visible={scene === 2}
            aria-hidden={scene !== 2}
          >
            <div className={styles.sectionLabel}>
              <span>02 / THREE LIVE OPTIONS</span>
              <b>FROM THE CATALOG</b>
            </div>
            <div className={styles.objects}>
              {products.map((product, index) => (
                <article
                  className={`${styles.object} ${styles[`object${index + 1}`]}`}
                  data-selected={product.id === story.recommended_product_id}
                  key={product.id}
                >
                  <Link
                    href={`/products/${encodeURIComponent(product.id)}`}
                    className={styles.objectLink}
                    tabIndex={scene === 2 ? 0 : -1}
                    aria-label={`View ${product.name}`}
                  >
                    <span className={styles.objectImage}>
                      <Image
                        src={product.image_url || ''}
                        alt={product.image_alt || product.name}
                        fill
                        sizes="(max-width: 700px) 30vw, 24vw"
                        loading={index === 0 ? 'eager' : 'lazy'}
                      />
                    </span>
                    <span className={styles.objectNumber}>0{index + 1}</span>
                    <span className={styles.objectBrand}>{product.brand || product.category}</span>
                    <strong className={styles.objectName}>{product.name}</strong>
                    <span className={styles.objectPrice}>{formatInr(product.price)}</span>
                  </Link>
                </article>
              ))}
            </div>
            <div className={styles.candidateFoot}>
              <span>Three distinct image-backed families</span>
              <i />
            </div>
          </div>

          <div
            className={styles.comparisonScene}
            data-story-view="comparison"
            data-visible={scene === 3}
            aria-hidden={scene !== 3}
          >
            <div className={styles.sectionLabel}>
              <span>03 / THE DIFFERENCE IS IN THE DETAIL</span>
              <b>CATALOG FACTS, ALIGNED</b>
            </div>
            <div className={styles.compareObjects}>
              {products.map((product, index) => (
                <div
                  className={`${styles.compareObject} ${styles[`object${index + 1}`]}`}
                  key={product.id}
                >
                  <span className={styles.compareImage}>
                    <Image
                      src={product.image_url || ''}
                      alt=""
                      fill
                      sizes="(max-width: 700px) 26vw, 20vw"
                      loading="lazy"
                    />
                  </span>
                </div>
              ))}
            </div>
            <svg
              className={styles.connectorMap}
              viewBox="0 0 1000 400"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <path d="M160 125 C160 270 160 270 160 352 M500 125 C500 270 500 270 500 352 M840 125 C840 270 840 270 840 352" />
              <path d="M160 352 H840" />
              <circle cx="160" cy="352" r="4" />
              <circle cx="500" cy="352" r="4" />
              <circle cx="840" cy="352" r="4" />
            </svg>
            <div className={styles.factOrbit}>
              {visibleComparisonValues.map((fact, index) => (
                <div className={`${styles.factLine} ${styles[`fact${index + 1}`]}`} key={fact.key}>
                  <span>{fact.label}</span>
                  {fact.values.map((value, valueIndex) => (
                    <b key={`${fact.key}-${products[valueIndex].id}`}>{value}</b>
                  ))}
                </div>
              ))}
            </div>
            <p className={styles.factsDisclaimer}>
              Published specifications only · no unverified performance claims
            </p>
          </div>

          <div
            className={styles.decisionScene}
            data-story-view="recommendation"
            data-visible={scene === 4}
            aria-hidden={scene !== 4}
          >
            <div className={styles.sectionLabel}>
              <span>04 / SHOPSMART ANALYSIS</span>
              <b>BEST FIT</b>
            </div>
            <div className={styles.decisionProduct}>
              <span className={styles.decisionImage}>
                <Image
                  src={selected.image_url || ''}
                  alt=""
                  fill
                  sizes="(max-width: 700px) 68vw, 42vw"
                  loading="lazy"
                />
              </span>
              <div className={styles.decisionHalo} />
              <span className={styles.bestFitStamp}>
                BEST
                <br />
                FIT
              </span>
            </div>
            <div className={styles.decisionCopy}>
              <p className={styles.overline}>A CLEARER CALL</p>
              <h2>{selected.name}</h2>
              <p className={styles.decisionReason}>{story.recommendation}</p>
              <div className={styles.evidenceList}>{evidenceFor(story)}</div>
              <strong className={styles.decisionPrice}>{formatInr(selected.price)}</strong>
              <span className={styles.budgetDelta}>
                {formatInr(story.savings_minor)} below your budget
              </span>
            </div>
            <div className={styles.recedingProducts} aria-hidden="true">
              {products
                .filter((product) => product.id !== selected.id)
                .map((product, index) => (
                  <span
                    className={styles.recedingProduct}
                    key={product.id}
                    style={{ '--offset': index } as CSSProperties}
                  >
                    <Image src={product.image_url || ''} alt="" fill sizes="12vw" loading="lazy" />
                  </span>
                ))}
            </div>
          </div>

          <div
            className={styles.commerceScene}
            data-story-view="commerce"
            data-visible={scene === 5}
            aria-hidden={scene !== 5}
          >
            <div className={styles.sectionLabel}>
              <span>05 / WHEN YOU’RE READY</span>
              <b>THE CHOICE IS YOURS</b>
            </div>
            <div className={styles.commerceObject}>
              <span className={styles.commerceImage}>
                <Image
                  src={selected.image_url || ''}
                  alt=""
                  fill
                  sizes="(max-width: 700px) 58vw, 36vw"
                  loading="lazy"
                />
              </span>
              <div className={styles.commerceCopy}>
                <span className={styles.overline}>SELECTED FROM THE LIVE CATALOG</span>
                <h2>{selected.name}</h2>
                <p>
                  {selected.stock_quantity} in stock <i /> {selected.brand}
                </p>
                <strong>{formatInr(selected.price)}</strong>
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
            </div>
            <div
              className={styles.cartFlight}
              data-flying={cartState === 'added'}
              aria-hidden="true"
            >
              <Image src={selected.image_url || ''} alt="" fill sizes="120px" />
            </div>
            <div
              className={styles.cartDestination}
              data-arrived={cartState === 'added'}
              aria-live="polite"
            >
              <span>YOUR CART</span>
              <b>{cart?.items.reduce((total, item) => total + item.quantity, 0) ?? 0}</b>
              {cartState === 'added' && <i aria-hidden="true">✓</i>}
            </div>
            {offer && (
              <div className={styles.offerPanel}>
                <span className={styles.overline}>LIVE OFFER · CART CHECKS ELIGIBILITY</span>
                <strong>{offer.name}</strong>
                <p>
                  {offer.discount_type === 'percentage'
                    ? `${offer.discount_value}% off eligible items`
                    : `${formatInr(offer.discount_value)} off eligible items`}
                </p>
                {(cartState === 'added' || selectedAlreadyAdded) && (
                  <form className={styles.couponForm} onSubmit={applyOffer}>
                    <label className="sr-only" htmlFor="hero-offer-code">
                      Offer code
                    </label>
                    <input
                      id="hero-offer-code"
                      value={coupon}
                      onChange={(event) => setCoupon(event.target.value)}
                      placeholder="Enter offer code"
                      autoComplete="off"
                    />
                    <button type="submit" disabled={!coupon.trim()}>
                      CHECK & APPLY
                    </button>
                  </form>
                )}
                {couponMessage && (
                  <span className={styles.couponResult} role="status">
                    {couponMessage}
                  </span>
                )}
                {hasVerifiedOffer && (
                  <b className={styles.verifiedDiscount}>
                    CART VERIFIED · −{formatInr(discount)} · NEW TOTAL {formatInr(finalPrice)}
                  </b>
                )}
                {cartState !== 'added' && !selectedAlreadyAdded && (
                  <small>Add the selected product to check this offer against your cart.</small>
                )}
              </div>
            )}
            <Link
              href={`/products/${encodeURIComponent(selected.id)}`}
              className={styles.detailLink}
            >
              Read the full product detail <span aria-hidden="true">↗</span>
            </Link>
          </div>

          <div className={styles.sceneNav} aria-label="Shopping story progress">
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
                <span>0{index + 1}</span>
                <b>{step.label}</b>
              </button>
            ))}
          </div>
          <p className={styles.scrollCue} aria-hidden="true">
            <span>SCROLL TO MOVE THROUGH THE DECISION</span>
            <i>↓</i>
          </p>
        </div>

        <div className={styles.releaseCue} aria-hidden="true">
          <span>YOUR NEXT FIND IS JUST BELOW</span>
          <i />
        </div>
        <div className={styles.releaseStorefront}>
          <p>THE STORY CONTINUES IN THE CATALOG</p>
          <h2>Browse by category</h2>
          <nav aria-label="Browse catalog categories">
            {categories.slice(0, 3).map((category, index) => (
              <Link
                href={`/products?category=${encodeURIComponent(category.value)}`}
                key={category.value}
              >
                <i>0{index + 1}</i>
                <b>{category.label}</b>
                <small>{category.count} listings</small>
              </Link>
            ))}
          </nav>
        </div>
        <Link
          href={`/products/${encodeURIComponent(selected.id)}`}
          className={styles.releasePreview}
          aria-label={`Continue with ${selected.name} in the live catalog`}
        >
          <span className={styles.releaseImage}>
            <Image src={selected.image_url || ''} alt="" fill sizes="72px" />
          </span>
          <span className={styles.releaseCopy}>
            <i>FROM THE DECISION TO THE CATALOG</i>
            <b>{selected.name}</b>
            <small>{formatInr(selected.price)} · View product</small>
          </span>
          <span className={styles.releaseArrow} aria-hidden="true">
            ↗
          </span>
        </Link>
      </div>

      <div className={styles.reducedStory} data-reduced-story="true">
        <div className={styles.reducedIntro}>
          <p className={styles.overline}>SHOPSMART INTELLIGENCE · A LIVE CATALOG</p>
          <h2>
            BUY WITH <em>CLARITY.</em>
          </h2>
          <p>{story.query}</p>
        </div>
        <div className={styles.reducedCandidates}>
          {products.map((product) => (
            <article key={product.id} data-recommended={product.id === selected.id}>
              <Image
                src={product.image_url || ''}
                alt={product.image_alt || product.name}
                width={360}
                height={360}
              />
              <span>{product.brand}</span>
              <h3>{product.name}</h3>
              <b>{formatInr(product.price)}</b>
              {product.id === selected.id && <p>BEST FIT · {story.recommendation}</p>}
            </article>
          ))}
        </div>
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
              : 'ADD SELECTED TO CART'}
        </button>
        <p role="status">
          {cartMessage || (selectedAlreadyAdded ? 'This product is in your cart.' : '')}
        </p>
      </div>
    </section>
  );
}
