'use client';

import { useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Button } from '@/components/ui/Button';

/**
 * ShopSmart AI hero — cinematic hybrid: real photography + AI overlay.
 *
 * LAYER MODEL (bottom → top):
 * 1. PHOTO (LCP): /images/hero-smart-mirror-clean.png — real shopper at a
 *    smart mirror in a warm boutique. Rendered statically with next/image
 *    priority; never hidden behind animation or JS gating (the previous
 *    onLoad-gated photo never revealed on cached loads, leaving visitors
 *    with the illustrated fallback).
 * 2. SCRIMS: plum brand unifier + legibility gradients (opacity entrance).
 * 3. AI OVERLAY: lightweight inline SVG confined to the visual half — thin
 *    orbit rings, detection brackets, particles, connection line, and one
 *    synced 10s scan event. Decorative: aria-hidden + pointer-events none.
 * 4. UI TIER: real HTML copy + CTAs + truthful capability chips.
 *
 * Chips are truthful capability signals only — no products, prices,
 * inventory, match scores or analytics. CTA targets existing routes only.
 * All continuous motion is transform/opacity CSS keyframes; the global
 * prefers-reduced-motion rule in globals.css collapses it to final state.
 */

/* ── Palette shortcuts (tokens defined in globals.css @theme) ──────────── */
const ACCENT_200 = 'var(--color-accent-200)';
const ACCENT_300 = 'var(--color-accent-300)';
const CHAMPAGNE = 'var(--color-clay-200)';

/* ── AI scan event ────────────────────────────────────────────────────────
   One 10s cycle; every participating element shares the same duration and
   delay so the scene reads as a single quiet event (~2s active, ~8s idle). */
const SCAN_DURATION_S = 10;
const SCAN_DELAY_S = 1.2;

/* Drifting AI particles over the visual half: [x, y, r, delay, dur].
   Coordinates live in the 1200x800 SVG viewBox space of the overlay. */
const PARTICLES: Array<[number, number, number, number, number]> = [
  [264, 240, 1.6, 0, 7],
  [456, 144, 1.4, 1.3, 8],
  [672, 208, 1.8, 0.6, 6.5],
  [840, 112, 1.3, 2.1, 7.5],
  [360, 496, 1.5, 1.7, 8.5],
  [576, 592, 1.2, 0.9, 6.8],
  [792, 464, 1.7, 2.6, 7.2],
  [984, 320, 1.4, 0.3, 8.2],
  [192, 384, 1.2, 3.1, 7.8],
  [1032, 544, 1.3, 1.1, 6.2],
];

/* Minimal particle set for mobile/tablet (single column): right-side band
   over the photo's subject, clear of headline/CTA text. 100x160 viewBox. */
const MOBILE_PARTICLES: Array<[number, number, number, number, number]> = [
  [52, 62, 0.6, 0, 7],
  [68, 74, 0.5, 1.4, 8],
  [84, 58, 0.7, 0.7, 6.5],
  [60, 96, 0.5, 2.2, 7.5],
  [78, 112, 0.6, 1.1, 8.2],
  [90, 88, 0.5, 2.9, 6.8],
];

export function HeroCampaign() {
  const sectionRef = useRef<HTMLElement | null>(null);

  /* ── Parallax (desktop, fine pointer, motion allowed) ───────────────────
     Event-based only — no continuous rAF loop. A throttled pointermove
     handler writes --par-x/--par-y in [-1, 1]; four depth layers translate
     via calc() in CSS. The listener attaches once and only when eligible. */
  const [parallaxReady, setParallaxReady] = useState(false);
  const parRaf = useRef<number>(0);

  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;

    const fineDesktop = window.matchMedia('(min-width: 1024px) and (pointer: fine)');
    const calmMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (!fineDesktop.matches || calmMotion.matches) return;

    setParallaxReady(true);

    let pending = false;
    const onMove = (event: PointerEvent) => {
      if (pending) return;
      pending = true;
      parRaf.current = window.requestAnimationFrame(() => {
        pending = false;
        const rect = section.getBoundingClientRect();
        const x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        const y = ((event.clientY - rect.top) / rect.height) * 2 - 1;
        section.style.setProperty('--par-x', x.toFixed(3));
        section.style.setProperty('--par-y', y.toFixed(3));
      });
    };
    const onLeave = () => {
      section.style.setProperty('--par-x', '0');
      section.style.setProperty('--par-y', '0');
    };

    section.addEventListener('pointermove', onMove);
    section.addEventListener('pointerleave', onLeave);
    return () => {
      section.removeEventListener('pointermove', onMove);
      section.removeEventListener('pointerleave', onLeave);
      window.cancelAnimationFrame(parRaf.current);
    };
  }, []);

  /* Chip entrance: flip one rAF after hydration so the CSS transition plays. */
  const [chipsIn, setChipsIn] = useState(false);
  useEffect(() => {
    const id = window.requestAnimationFrame(() => setChipsIn(true));
    return () => window.cancelAnimationFrame(id);
  }, []);

  return (
    <section
      ref={sectionRef}
      className={`hero-parallax relative overflow-hidden bg-ink-900 ${parallaxReady ? 'hero-parallax-live' : ''}`}
      style={{ '--par-x': '0', '--par-y': '0' } as React.CSSProperties}
    >
      {/* ── Layer 1: photo (LCP — static, never gated) ─────────────────── */}
      <div className="par-photo absolute inset-0" aria-hidden="true">
        <Image
          src="/images/hero-smart-mirror-clean.png"
          alt=""
          fill
          priority
          sizes="100vw"
          quality={82}
          className="object-cover object-[68%_center]"
        />
      </div>

      {/* ── Layer 2: brand unifier + legibility scrims ─────────────────── */}
      <div
        aria-hidden="true"
        className="par-scrim hero-scrim-in pointer-events-none absolute -inset-1 z-10 bg-accent-900/15"
      />
      <div
        aria-hidden="true"
        className="hero-scrim-in pointer-events-none absolute inset-0 z-10 bg-gradient-to-r from-ink-900/85 via-ink-900/40 to-transparent"
        style={{ animationDelay: '450ms' }}
      />
      <div
        aria-hidden="true"
        className="hero-scrim-in pointer-events-none absolute inset-x-0 bottom-0 z-10 h-1/4 bg-gradient-to-t from-ink-900/60 to-transparent"
        style={{ animationDelay: '600ms' }}
      />

      {/* ── Layer 3: AI intelligence overlay (SVG, decorative) ─────────── */}
      <svg
        aria-hidden="true"
        className="par-overlay pointer-events-none absolute inset-y-0 right-0 z-20 hidden h-full lg:block"
        width="62%"
        viewBox="0 0 1200 800"
        preserveAspectRatio="xMidYMid slice"
        fill="none"
      >
        {/* Orbit rings — thin, elliptical, counter-rotating. Entrance reveal
            sits on the outer group so spin (transform) and fade (opacity)
            never fight over the same element's animation slot. */}
        <g className="ai-reveal" style={{ animationDelay: '650ms' }}>
          <g className="hero-orbit-a">
            <ellipse
              cx="640"
              cy="400"
              rx="330"
              ry="200"
              stroke={ACCENT_200}
              strokeOpacity="0.35"
              strokeWidth="1"
              strokeDasharray="2 10"
              transform="rotate(-14 640 400)"
            />
          </g>
        </g>
        <g className="ai-reveal" style={{ animationDelay: '850ms' }}>
          <g className="hero-orbit-b">
            <ellipse
              cx="640"
              cy="400"
              rx="255"
              ry="308"
              stroke={CHAMPAGNE}
              strokeOpacity="0.28"
              strokeWidth="1"
              strokeDasharray="1 12"
              transform="rotate(12 640 400)"
            />
          </g>
        </g>

        {/* Detection frame — corner brackets around the mirror zone */}
        <g className="ai-reveal" style={{ animationDelay: '750ms' }}>
          <g className="ai-detect" stroke={CHAMPAGNE} strokeWidth="1.5" strokeLinecap="round">
            <path d="M436 176 v-26 h26" />
            <path d="M844 150 h26 v26" />
            <path d="M870 624 v26 h-26" />
            <path d="M462 650 h-26 v-26" />
          </g>
        </g>

        {/* Connection lines — mirror zone → chip tier (illuminate on scan) */}
        <g className="ai-reveal" style={{ animationDelay: '900ms' }}>
          <path
            className="ai-line"
            d="M700 430 C 780 470, 850 500, 930 520"
            stroke={ACCENT_300}
            strokeOpacity="0.5"
            strokeWidth="1.2"
            strokeDasharray="3 7"
          />
          <path
            className="ai-line"
            d="M660 470 C 720 540, 780 590, 850 640"
            stroke={CHAMPAGNE}
            strokeOpacity="0.4"
            strokeWidth="1.2"
            strokeDasharray="2 8"
          />
        </g>

        {/* Particles — tiny, staggered, transform/opacity only */}
        <g className="ai-reveal" style={{ animationDelay: '800ms' }}>
          {PARTICLES.map(([x, y, r, delay, dur], i) => (
            <circle
              key={i}
              className={`ai-particle ${i === 2 || i === 6 ? 'ai-particle-sync' : ''}`}
              cx={x}
              cy={y}
              r={r}
              fill={i % 3 === 0 ? CHAMPAGNE : ACCENT_200}
              style={{ '--pd': `${dur}s`, '--pd-delay': `${delay}s` } as React.CSSProperties}
            />
          ))}
        </g>
      </svg>

      {/* Signature scan band — travels across the mirror zone (10s cycle).
          Full-width on single-column screens; right 62% on desktop so it
          never crosses the headline. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 left-0 right-0 z-20 overflow-hidden lg:left-auto lg:w-[62%]"
      >
        <div
          className="ai-scan"
          style={{ animationDuration: `${SCAN_DURATION_S}s`, animationDelay: `${SCAN_DELAY_S}s` }}
        />
      </div>

      {/* Mobile/tablet particle layer — minimal AI presence: a few drifting
          points over the photo's subject; no rings, brackets or lines. */}
      <svg
        aria-hidden="true"
        className="par-overlay pointer-events-none absolute inset-0 z-20 h-full w-full lg:hidden"
        viewBox="0 0 100 160"
        preserveAspectRatio="xMidYMid slice"
        fill="none"
      >
        <g className="ai-reveal" style={{ animationDelay: '800ms' }}>
          {MOBILE_PARTICLES.map(([x, y, r, delay, dur], i) => (
            <circle
              key={i}
              className={`ai-particle ${i === 1 || i === 4 ? 'ai-particle-sync' : ''}`}
              cx={x}
              cy={y}
              r={r}
              fill={i % 3 === 0 ? CHAMPAGNE : ACCENT_200}
              style={{ '--pd': `${dur}s`, '--pd-delay': `${delay}s` } as React.CSSProperties}
            />
          ))}
        </g>
      </svg>

      {/* ── Layer 4: UI tier — real HTML copy + CTAs ───────────────────── */}
      <div className="relative z-30 mx-auto grid max-w-7xl grid-cols-1 items-center gap-10 px-4 pb-16 pt-12 sm:px-6 sm:pb-20 sm:pt-16 lg:min-h-[43rem] lg:grid-cols-[1.05fr_0.95fr] lg:gap-6 lg:px-8 lg:pb-16 lg:pt-14">
        <div className="relative text-center lg:text-left">
          <p
            className="hero-rise text-xs font-semibold uppercase tracking-caps text-accent-300"
            style={{ animationDelay: '150ms' }}
          >
            New Season · The AI Edit
          </p>

          <h1 className="font-display font-bold tracking-display text-blush-50 text-balance text-display-md sm:text-[4rem] sm:leading-[1.02] lg:text-[clamp(4.25rem,4.6vw,6.5rem)] lg:leading-[0.97] lg:max-w-none lg:w-[112%]">
            <span className="hero-mask">
              <span className="hero-mask-inner" style={{ animationDelay: '300ms' }}>
                Style, Curated
              </span>
            </span>
            <span className="hero-mask pb-2">
              <span
                className="hero-mask-inner shimmer-text block bg-gradient-to-r from-accent-200 via-clay-200 to-accent-300 bg-clip-text italic text-transparent"
                style={{ animationDelay: '420ms' }}
              >
                Intelligence
              </span>
            </span>
          </h1>

          {/* Self-drawing swash beneath the accent word */}
          <svg
            aria-hidden="true"
            viewBox="0 0 320 14"
            className="mx-auto mt-1 h-3.5 w-56 text-accent-300 sm:w-72 lg:mx-0 lg:-mt-2 lg:w-[24rem]"
          >
            <path
              className="hero-draw"
              d="M4 10 C 60 2, 140 2, 200 7 C 245 11, 290 9, 316 4"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              pathLength={1}
            />
          </svg>

          <p
            className="hero-rise mx-auto mt-6 max-w-xl text-base leading-relaxed text-ink-100/85 sm:text-lg lg:mx-0"
            style={{ animationDelay: '500ms' }}
          >
            A premium shopping experience with a secure, AI-assisted account foundation — built for
            confidence from sign-up to sign-in.
          </p>

          <div
            className="hero-rise mt-8 flex flex-col items-center justify-center gap-4 pt-1 sm:flex-row lg:justify-start"
            style={{ animationDelay: '650ms' }}
          >
            <Link
              href="/auth/register"
              className="w-full rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-300 focus-visible:ring-offset-2 sm:w-auto"
            >
              <Button
                variant="primary"
                size="lg"
                className="w-full bg-blush-50! text-accent-800! shadow-editorial hover:bg-white! sm:w-auto"
              >
                Create Account
              </Button>
            </Link>
            <Link
              href="/auth/login"
              className="w-full rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-300 sm:w-auto"
            >
              <Button
                variant="secondary"
                size="lg"
                className="w-full bg-transparent! text-accent-100! border-accent-300/70! hover:border-accent-200! hover:bg-white/10! sm:w-auto"
              >
                Sign In
              </Button>
            </Link>
          </div>

          {/* Trust markers — true of the existing account foundation only */}
          <ul
            className="hero-rise mt-7 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs font-medium text-ink-100/70 lg:justify-start"
            style={{ animationDelay: '800ms' }}
          >
            {['Encrypted credentials', 'HttpOnly sessions', 'Single-device sign-in'].map(
              (marker) => (
                <li key={marker} className="inline-flex items-center gap-1.5">
                  <svg aria-hidden="true" viewBox="0 0 12 11" className="h-3 w-3" fill={CHAMPAGNE}>
                    <path d="M2 10 C 2 4, 6 1, 11 0 C 11 6, 8 10, 2 10 Z" />
                  </svg>
                  {marker}
                </li>
              )
            )}
          </ul>
        </div>

        {/* Right grid column: occupied visually by photo + AI overlay */}
        <div aria-hidden="true" className="hidden lg:block" />
      </div>

      {/* ── Truthful capability chips (desktop only — single-column layouts
          keep the claims in copy/trust markers, no floating overlays) ──── */}
      <div className="par-chips pointer-events-none absolute inset-0 z-30 hidden lg:block">
        <Chip
          label="AI-assisted"
          icon={
            <path d="M6 1.5 C 6.8 3.5, 8.5 5.2, 10.5 6 C 8.5 6.8, 6.8 8.5, 6 10.5 C 5.2 8.5, 3.5 6.8, 1.5 6 C 3.5 5.2, 5.2 3.5, 6 1.5 Z" />
          }
          iconStroke="var(--color-accent-600)"
          position="right-[5%] top-[20%]"
          visible={chipsIn}
          enterDelay={950}
          driftDelay={0}
        />
        <Chip
          label="Curated experience"
          icon={<circle cx="6" cy="6" r="4.4" />}
          iconStroke="var(--color-clay-400)"
          position="bottom-[26%] right-[7%] hidden lg:block"
          visible={chipsIn}
          enterDelay={1150}
          driftDelay={1.4}
        />
        <Chip
          label="Secure session"
          icon={
            <>
              <path d="M6 1 L 9.5 2.5 V 5.5 C 9.5 8, 8 9.7, 6 10.7 C 4 9.7, 2.5 8, 2.5 5.5 V 2.5 Z" />
              <path d="M4.4 5.8 L 5.6 7 L 7.8 4.6" />
            </>
          }
          iconStroke="var(--color-leaf-600)"
          position="bottom-[38%] right-[24%] hidden sm:block"
          visible={chipsIn}
          enterDelay={1100}
          driftDelay={2.8}
        />
        <Chip
          label="ShopSmart AI"
          position="bottom-[10%] right-[28%]"
          visible={chipsIn}
          enterDelay={1250}
          driftDelay={4.2}
        />
      </div>

      {/* Brand medallion (desktop only — collides with the headline on
          single-column layouts) */}
      <div className="absolute right-[3%] top-[8%] z-30 hidden lg:block">
        <span className="flex h-14 w-14 items-center justify-center rounded-full border border-accent-300/50 bg-white/10 shadow-tile backdrop-blur-[2px]">
          <span className="font-display text-2xl font-bold leading-none text-accent-200 select-none">
            S
          </span>
        </span>
      </div>

      {/* Bottom edge separation */}
      <div
        aria-hidden="true"
        className="absolute inset-x-0 bottom-0 z-30 h-px bg-gradient-to-r from-transparent via-accent-400/50 to-transparent"
      />
    </section>
  );
}

/* ── Truthful chip: opacity entrance (staggered) → ambient drift ─────────
   Outer wrapper owns entrance + parallax transform; the inner pill owns the
   drift keyframes, so no element carries two competing animations. */
function Chip({
  label,
  icon,
  iconStroke,
  position,
  visible,
  enterDelay,
  driftDelay,
}: {
  label: string;
  icon?: React.ReactNode;
  iconStroke?: string;
  position: string;
  visible: boolean;
  enterDelay: number;
  driftDelay: number;
}) {
  return (
    <div
      className={`hero-chip-enter absolute ${position} ${visible ? 'is-visible' : ''}`}
      style={
        {
          '--enter-delay': `${enterDelay}ms`,
          '--chip-drift-delay': `${driftDelay}s`,
        } as React.CSSProperties
      }
    >
      <span className="hero-chip-float pointer-events-auto inline-flex items-center gap-1.5 rounded-full border border-accent-200 bg-white/95 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-caps text-accent-800 shadow-tile transition-colors duration-300">
        {icon && (
          <svg
            aria-hidden="true"
            viewBox="0 0 12 12"
            className="h-3 w-3"
            fill="none"
            stroke={iconStroke}
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {icon}
          </svg>
        )}
        {label}
      </span>
    </div>
  );
}
