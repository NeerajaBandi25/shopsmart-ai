'use client';

import Image from 'next/image';
import React from 'react';

/**
 * Photographic editorial category card — one frame of a single retail
 * photography campaign (warm cream / plum / champagne, cinematic light).
 *
 * Hierarchy: photograph → cinematic gradient → editorial metadata →
 * category name. All text is real DOM; nothing is baked into the images.
 * Cards are visual-only discovery (the section copy says so) — no invented
 * navigation, no fake recommendations. Hover/pointer is a restrained
 * "curated discovery" reveal: slight image scale/brighten, deeper gradient,
 * title lift, thin border highlight, small directional cue. Label and
 * metadata are always visible (no hover-only content for AT/keyboard).
 */

export interface CategoryCardProps {
  numeral: string;
  name: string;
  image: string;
  alt: string;
  badge: string;
  /** Per-asset focal point — tuned per photograph, not one size for all. */
  objectPosition?: string;
}

export function CategoryCard({
  numeral,
  name,
  image,
  alt,
  badge,
  objectPosition = '50% 50%',
}: CategoryCardProps) {
  return (
    <article className="cat-card group relative aspect-[4/3] w-full overflow-hidden rounded-tile border border-transparent bg-ink-900 shadow-tile transition-[transform,border-color,box-shadow] duration-500 ease-luxe hover:-translate-y-1 hover:border-accent-300/50 hover:shadow-tile-hover">
      {/* Photograph — dominant visual, lazy (below the hero), Next-optimized */}
      <Image
        src={image}
        alt={alt}
        fill
        loading="lazy"
        quality={78}
        sizes="(min-width: 1024px) 33vw, 50vw"
        className="cat-img absolute inset-0 object-cover transition-transform duration-700 ease-luxe group-hover:translate-x-[1%] group-hover:scale-[1.05]"
        style={{ objectPosition }}
      />

      {/* Warm cinematic base gradient */}
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-gradient-to-t from-ink-900/85 via-ink-900/15 to-accent-900/10"
      />
      {/* Deepening layer on hover (opacity only) */}
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-ink-900/15 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
      />

      {/* Editorial badge — top left */}
      <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full border border-white/25 bg-ink-900/35 px-2.5 py-1 text-[8px] font-semibold uppercase tracking-caps text-blush-50 backdrop-blur-[2px] sm:text-[9px]">
        <span aria-hidden="true" className="h-1 w-1 rounded-full bg-clay-300" />
        {badge}
      </span>

      {/* Editorial numbering — top right */}
      <span
        aria-hidden="true"
        className="absolute right-3 top-3 select-none text-[9px] font-semibold uppercase tracking-caps text-blush-50/60 sm:text-[10px]"
      >
        Nº {numeral}
      </span>

      {/* Metadata + name — always visible, lifts a few px on hover */}
      <div className="absolute inset-x-0 bottom-0 p-3 transition-transform duration-500 ease-luxe group-hover:-translate-y-1 sm:p-4">
        <p className="mb-1 flex items-center gap-1.5 text-[8px] font-semibold uppercase tracking-caps text-accent-200/90 sm:text-[9px]">
          <svg aria-hidden="true" viewBox="0 0 10 10" className="h-2 w-2" fill="currentColor">
            <path d="M5 0.8 C 5.6 2.8, 7.2 4.4, 9.2 5 C 7.2 5.6, 5.6 7.2, 5 9.2 C 4.4 7.2, 2.8 5.6, 0.8 5 C 2.8 4.4, 4.4 2.8, 5 0.8 Z" />
          </svg>
          ShopSmart
        </p>
        <h3 className="text-[13px] font-semibold uppercase leading-tight tracking-wide text-white sm:text-sm">
          {name}
        </h3>
      </div>

      {/* Directional cue — understated, appears on hover */}
      <span
        aria-hidden="true"
        className="absolute bottom-3 right-3 flex h-7 w-7 translate-x-[-6px] items-center justify-center rounded-full border border-clay-200/50 bg-ink-900/30 text-clay-200 opacity-0 backdrop-blur-[2px] transition-all duration-500 ease-luxe group-hover:translate-x-0 group-hover:opacity-100 sm:bottom-4 sm:right-4"
      >
        <svg
          viewBox="0 0 12 12"
          className="h-3 w-3"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M2.5 6 H 9.5 M6.5 3 L 9.5 6 L 6.5 9" />
        </svg>
      </span>
    </article>
  );
}
