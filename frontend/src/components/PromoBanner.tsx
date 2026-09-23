'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/Button';

/**
 * Closing promo band + footer, composed inline (no new component file).
 * CTAs use existing routes only; no commerce behavior. Footer links point to
 * existing routes exclusively (Home / Sign in / Create account). Button
 * variant colors are overridden with `!` utilities so the primary CTA reads
 * as white-on-berry (contrast) — Button.tsx itself stays frozen.
 */
export function PromoBanner() {
  const year = new Date().getFullYear();

  return (
    <>
      {/* ── Closing CTA band ─────────────────────────────────────────── */}
      <div className="relative overflow-hidden border-t border-white/10 bg-gradient-to-br from-accent-700 via-accent-600 to-accent-800">
        {/* Decorative depth: glows + botanical silhouette (brand-own SVG) */}
        <div aria-hidden="true" className="absolute -top-20 -left-16 h-64 w-64 rounded-full bg-accent-400/25 blur-3xl" />
        <div aria-hidden="true" className="absolute -bottom-24 -right-16 h-72 w-72 rounded-full bg-accent-900/45 blur-3xl" />
        <svg
          aria-hidden="true"
          viewBox="0 0 120 160"
          className="absolute -bottom-4 left-[6%] hidden h-40 w-auto opacity-25 lg:block"
        >
          <g fill="var(--color-accent-300)">
            <path d="M60 158 C 56 118, 58 76, 66 34" stroke="var(--color-accent-300)" strokeWidth="2.5" fill="none" strokeLinecap="round" />
            <path d="M64 46 C 52 44, 42 34, 40 18 C 56 20, 64 30, 64 46 Z" />
            <path d="M63 66 C 74 62, 82 52, 83 36 C 68 40, 62 50, 63 66 Z" />
            <path d="M61 88 C 49 86, 40 76, 38 60 C 54 62, 61 72, 61 88 Z" />
            <path d="M62 110 C 73 106, 81 96, 82 80 C 67 84, 61 94, 62 110 Z" />
          </g>
        </svg>

        <div className="relative max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16 text-center">
          <p className="text-xs font-semibold uppercase tracking-caps text-accent-200">
            The Member Edit
          </p>
          <h2 className="mt-3.5 font-display text-display-md sm:text-display-lg font-bold tracking-display text-white text-balance">
            Your Premium Shopping Assistant Awaits
          </h2>

          {/* Ornamental divider: quiet editorial punctuation */}
          <div aria-hidden="true" className="mx-auto mt-6 flex w-24 items-center justify-center gap-2">
            <span className="h-px flex-1 bg-accent-300/60" />
            <span className="h-1 w-1 rounded-full bg-accent-300" />
            <span className="h-px flex-1 bg-accent-300/60" />
          </div>

          <p className="mt-5 max-w-xl mx-auto text-base text-accent-100">
            Create your account to experience secure, AI-assisted membership from
            your very first sign-in.
          </p>

          <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/auth/register"
              className="w-full rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 sm:w-auto"
            >
              <Button
                variant="primary"
                size="lg"
                className="w-full sm:w-auto bg-white! text-accent-700! hover:bg-accent-50! shadow-editorial"
              >
                Get Started
              </Button>
            </Link>
            <Link
              href="/auth/login"
              className="w-full rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 sm:w-auto"
            >
              <Button
                variant="secondary"
                size="lg"
                className="w-full sm:w-auto border-white/70! text-white! hover:bg-white/10!"
              >
                Sign In
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* ── Footer (inline, existing routes only) ────────────────────── */}
      <footer className="bg-ink-900 text-ink-300">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-12">
          <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.4fr_1fr_1fr]">
            {/* Brand block */}
            <div>
              <p className="font-display text-xl font-bold text-white">
                ShopSmart <span className="text-accent-400">AI</span>
              </p>
              <p className="mt-3 max-w-sm text-sm leading-relaxed">
                A premium shopping destination with a secure, AI-assisted
                account foundation. Commerce features are planned — the design
                vision ships today.
              </p>
              <p className="mt-4 inline-flex items-center gap-2 rounded-full border border-white/15 px-3.5 py-1.5 text-[10px] font-semibold uppercase tracking-caps text-ink-300">
                <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-leaf-500" />
                Secure by design
              </p>
            </div>

            {/* Explore — existing routes only */}
            <nav aria-label="Footer">
              <p className="text-xs font-semibold uppercase tracking-caps text-accent-400">
                Explore
              </p>
              <ul className="mt-4 space-y-2.5 text-sm">
                <li><Link href="/" className="transition-colors hover:text-white">Home</Link></li>
                <li><Link href="/auth/login" className="transition-colors hover:text-white">Sign in</Link></li>
                <li><Link href="/auth/register" className="transition-colors hover:text-white">Create account</Link></li>
              </ul>
            </nav>

            {/* The AI Edit — honest capability list (mirrors homepage) */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-caps text-accent-400">
                The AI Edit
              </p>
              <ul className="mt-4 space-y-2.5 text-sm">
                <li>Secure account foundation — <span className="text-white font-medium">Available</span></li>
                <li>Recommendations, visual search, trends — <span className="text-ink-300">Planned</span></li>
              </ul>
              <p className="mt-5 text-xs leading-relaxed text-ink-300/80">
                Planned capabilities are under future consideration and are not
                part of the current product.
              </p>
            </div>
          </div>

          <div className="mt-10 border-t border-white/10 pt-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-ink-300/70">
            <p>© {year} ShopSmart AI — design vision demo. No real commerce.</p>
            <p>Built as a portfolio production-system study.</p>
          </div>
        </div>
      </footer>
    </>
  );
}
