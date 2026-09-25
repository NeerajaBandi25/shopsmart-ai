'use client';

/**
 * AI identity/capability band. Describes existing AI capabilities (secure
 * account/session foundation) and clearly labels the conceptual features as
 * planned — no functionality is implied. Icons are brand-own inline SVG
 * (no emoji, no external assets).
 */

type CapabilityIcon = 'shield' | 'spark' | 'search' | 'trend';

function CapabilityGlyph({ icon }: { icon: CapabilityIcon }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 40 40"
      fill="none"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-9 w-9"
    >
      {icon === 'shield' && (
        <g stroke="var(--color-accent-200)">
          <path
            d="M20 5 L 32 10 V 20 C 32 28, 27 33, 20 36 C 13 33, 8 28, 8 20 V 10 Z"
            fill="rgba(199,126,158,0.18)"
          />
          <path d="M14 20 L 18.5 24.5 L 27 15" stroke="var(--color-accent-300)" />
        </g>
      )}
      {icon === 'spark' && (
        <g stroke="var(--color-white)">
          <path
            d="M20 6 C 21.5 13, 24 16.5, 31 18 C 24 19.5, 21.5 23, 20 30 C 18.5 23, 16 19.5, 9 18 C 16 16.5, 18.5 13, 20 6 Z"
            fill="rgba(255,255,255,0.10)"
          />
          <circle cx="31" cy="29" r="2" fill="var(--color-accent-400)" stroke="none" />
          <circle cx="10" cy="30" r="1.5" fill="var(--color-accent-400)" stroke="none" />
        </g>
      )}
      {icon === 'search' && (
        <g stroke="var(--color-white)">
          <circle cx="18" cy="18" r="10" />
          <path d="M25.5 25.5 L 33 33" />
          <path
            d="M13 18 C 15 14, 18 13.5, 20 15.5 C 22 17.5, 24 17, 23 20"
            stroke="var(--color-accent-300)"
            strokeWidth="1.8"
          />
        </g>
      )}
      {icon === 'trend' && (
        <g stroke="var(--color-white)">
          <path d="M6 30 L 15 21 L 21 26 L 34 12" />
          <path d="M27 12 H 34 V 19" />
          <circle cx="15" cy="21" r="1.8" fill="var(--color-accent-400)" stroke="none" />
          <circle cx="21" cy="26" r="1.8" fill="var(--color-accent-400)" stroke="none" />
        </g>
      )}
    </svg>
  );
}

interface Capability {
  icon: CapabilityIcon;
  title: string;
  copy: string;
  available: boolean;
}

const capabilities: Capability[] = [
  {
    icon: 'shield',
    title: 'Secure Foundation',
    copy: 'Encrypted credentials, protected sessions, and secure account management today.',
    available: true,
  },
  {
    icon: 'spark',
    title: 'Smart Recommendations',
    copy: 'Personalized suggestions from your preferences and browsing history.',
    available: false,
  },
  {
    icon: 'search',
    title: 'Visual Search',
    copy: 'Find products with images or natural-language descriptions.',
    available: false,
  },
  {
    icon: 'trend',
    title: 'Trend Analysis',
    copy: 'Stay ahead of fashion and lifestyle trends with AI-powered insight.',
    available: false,
  },
];

export function DiscoverySection() {
  return (
    <section className="relative overflow-hidden bg-ink-900">
      {/* Band depth: quiet berry glows so the section holds its own after the
          denser sections above */}
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[radial-gradient(ellipse_at_12%_0%,rgba(87,24,54,0.55),transparent_55%)]"
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[radial-gradient(ellipse_at_88%_100%,rgba(62,107,79,0.18),transparent_50%)]"
      />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
        <div className="text-center space-y-2.5">
          <p className="text-xs font-semibold uppercase tracking-caps text-accent-400">
            The AI Edit
          </p>
          <h2 className="font-display text-display-md sm:text-display-lg font-bold tracking-display text-white">
            Powered by Intelligent Retail
          </h2>
          <p className="max-w-2xl mx-auto text-base text-ink-300">
            ShopSmart AI pairs a premium storefront vision with an already-shipped security
            foundation.
          </p>
        </div>

        <div className="mt-9 sm:mt-11 grid gap-5 sm:gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {capabilities.map((capability) => (
            <div
              key={capability.title}
              className={`group relative rounded-tile border p-6 text-center transition-all duration-300 ease-luxe ${
                capability.available
                  ? 'border-accent-400/80 bg-gradient-to-b from-accent-700/65 to-accent-900/65 shadow-editorial ring-2 ring-accent-400/30 hover:-translate-y-1 hover:shadow-editorial'
                  : 'border-white/10 bg-white/[0.045] before:absolute before:inset-x-6 before:top-0 before:h-px before:bg-white/10 hover:-translate-y-0.5 hover:bg-white/[0.08]'
              }`}
            >
              <span
                aria-hidden="true"
                className="mx-auto mb-3.5 flex h-14 w-14 items-center justify-center rounded-full border border-white/15 bg-white/[0.06] shadow-tile transition-transform duration-300 ease-luxe group-hover:scale-110"
              >
                <CapabilityGlyph icon={capability.icon} />
              </span>
              <h3 className="font-semibold text-white mb-2">{capability.title}</h3>
              <p className="text-sm text-ink-300 leading-relaxed">{capability.copy}</p>

              {/* Availability badges: distinct truthful states — the live
                  capability is luminous, planned ones are deliberately quiet */}
              {capability.available ? (
                <p className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-accent-300 bg-accent-300/45 px-4 py-1.5 text-[10px] font-extrabold uppercase tracking-caps text-white shadow-[0_0_18px_rgba(195,126,158,0.5)] ring-1 ring-accent-200/60">
                  <span
                    aria-hidden="true"
                    className="h-2 w-2 rounded-full bg-accent-100 shadow-[0_0_8px_rgba(237,211,223,1)]"
                  />
                  Available now
                </p>
              ) : (
                <p className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-white/15 px-3.5 py-1 text-[10px] font-medium uppercase tracking-caps text-ink-300">
                  <span
                    aria-hidden="true"
                    className="h-1.5 w-1.5 rounded-full border border-ink-300"
                  />
                  Planned
                </p>
              )}
            </div>
          ))}
        </div>

        <p className="mt-9 text-center text-sm text-ink-300 max-w-2xl mx-auto">
          Smart Recommendations, Visual Search, and Trend Analysis are conceptual features planned
          for future implementation and are not currently available. Secure Foundation is available
          today and supports the registered-account experience.
        </p>
      </div>
    </section>
  );
}
