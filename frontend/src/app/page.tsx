import Link from 'next/link';
import Nav from '@/components/nav';
import { cookies } from 'next/headers';
import { HeroCampaign } from '@/components/HeroCampaign';
import { CategorySection } from '@/components/CategorySection';
import { DiscoverySection } from '@/components/DiscoverySection';
import { PromoBanner } from '@/components/PromoBanner';

/**
 * ShopSmart AI homepage — Phase 3 visual redesign.
 * Composes the existing merchandising components in the approved order:
 * Nav → Hero → Offer band → Categories → Discovery → Promo. Visual redesign
 * only: existing routes/CTAs, no commerce behavior, no search, no product
 * data. The offer band states only perks that are true today (secure account,
 * planned AI features framed as early access, free registration) — no
 * fabricated discounts or inventory.
 *
 * Section rhythm: sections own their vertical padding (py-12/py-16 range) so
 * bands sit flush and the page reads as one editorial composition.
 *
 * Auth probe optimization: the session cookie is HttpOnly, so client JS in
 * Nav cannot know whether it exists. This server component checks cookie
 * presence (presence only — no validation, no DB access, no auth decisions)
 * and tells Nav to skip the /auth/me probe when there is provably no cookie,
 * avoiding a request that could only ever return 401 for signed-out visitors.
 * A present cookie still gets the full probe (validation stays server-side
 * in the backend, unchanged).
 */
export default async function HomePage() {
  const cookieStore = cookies();
  const hasSessionCookie = cookieStore.has('session_id');

  return (
    <>
      <Nav probeAuth={hasSessionCookie} />
      <main>
        <HeroCampaign />

        {/* Founding Member Perks — honest offer band (Myntra-strip energy,
            truthful content: no fake discounts, no inventory claims) */}
        <section
          aria-label="Founding member perks"
          className="relative overflow-hidden bg-gradient-to-r from-accent-900 via-accent-800 to-accent-700"
        >
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-[radial-gradient(ellipse_at_18%_0%,rgba(246,217,194,0.20),transparent_52%)]"
          />
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-[radial-gradient(ellipse_at_85%_110%,rgba(62,107,79,0.28),transparent_55%)]"
          />
          <div aria-hidden="true" className="texture-grain absolute inset-0 opacity-[0.12]" />
          <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-7 flex flex-col lg:flex-row items-center justify-center gap-3 lg:gap-10 text-center">
            <p className="font-display text-lg sm:text-xl font-bold text-blush-50 whitespace-nowrap">
              Founding Member Perks
            </p>
            <ul className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-[11px] sm:text-xs font-semibold uppercase tracking-caps text-accent-100">
              {['Founding Member', 'Secure Account', 'AI-assisted experience', 'Free to Join'].map(
                (perk, i) => (
                  <li key={perk} className="flex items-center gap-3">
                    {i > 0 && (
                      <span aria-hidden="true" className="h-1 w-1 rounded-full bg-accent-300" />
                    )}
                    <span>{perk}</span>
                  </li>
                )
              )}
            </ul>
            <Link
              href="/auth/register"
              className="group inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-caps text-white/90 underline decoration-accent-300/60 decoration-1 underline-offset-4 transition-colors hover:text-white hover:decoration-white"
            >
              Create Account
              <span
                aria-hidden="true"
                className="transition-transform duration-300 ease-luxe group-hover:translate-x-0.5"
              >
                →
              </span>
            </Link>
          </div>
        </section>

        <CategorySection />
        <DiscoverySection />
        <PromoBanner />
      </main>
    </>
  );
}
