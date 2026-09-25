'use client';

import { CategoryCard } from '@/components/CategoryCard';

/**
 * Editorial category discovery — "nine premium worlds of shopping".
 *
 * One data-driven list (no duplicated card code); the photographs are the
 * approved local campaign assets and are referenced by their exact existing
 * filenames. Desktop: 3-column grid with generous, equal row breathing
 * space; tablet: 2 columns; mobile: optimized 2 columns. Cards are visual-only
 * discovery — the section copy keeps the honest disclaimer; no navigation,
 * no fake recommendations, no commerce claims.
 */

interface CategoryDef {
  numeral: string;
  name: string;
  image: string;
  alt: string;
  badge: string;
  /** Focal point tuned per photograph after visual inspection. */
  objectPosition?: string;
}

const categories: CategoryDef[] = [
  {
    numeral: '01',
    name: 'Fashion',
    image: '/images/Home-Page-Cat-Images/Fashion_main_cat.png',
    alt: 'Shopper browsing a clothing rack in a warm, softly lit boutique',
    badge: 'New In',
    objectPosition: '62% 40%',
  },
  {
    numeral: '02',
    name: 'Electronics',
    image: '/images/Home-Page-Cat-Images/Electronics_main_cat.png',
    alt: 'Headphones, phone, laptop and watch arranged on a marble desk',
    badge: 'Editors’ Pick',
    objectPosition: '50% 55%',
  },
  {
    numeral: '03',
    name: 'Home & Living',
    image: '/images/Home-Page-Cat-Images/HomeLiving_main_cat.png',
    alt: 'Living room with a cream sofa, burgundy throw and marble coffee table at sunset',
    badge: 'New In',
    objectPosition: '45% 60%',
  },
  {
    numeral: '04',
    name: 'Beauty & Personal Care',
    image: '/images/Home-Page-Cat-Images/BeautyPersonalCare_main_cat.png',
    alt: 'Skincare and candles on a marble vanity beside a woman at a lit mirror',
    badge: 'Curated',
    objectPosition: '50% 62%',
  },
  {
    numeral: '05',
    name: 'Sports & Outdoors',
    image: '/images/Home-Page-Cat-Images/SportsOutdoors_main_cat.png',
    alt: 'Athlete tying a trainer on a sunset terrace beside dumbbells and a yoga mat',
    badge: 'Active',
    objectPosition: '68% 45%',
  },
  {
    numeral: '06',
    name: 'Footwear',
    image: '/images/Home-Page-Cat-Images/Footwear_main_cat.png',
    alt: 'Sneakers and heels displayed on marble plinths in a boutique',
    badge: 'New In',
    objectPosition: '48% 58%',
  },
  {
    numeral: '07',
    name: 'Accessories',
    image: '/images/Home-Page-Cat-Images/Accessories_main_cat.png',
    alt: 'Burgundy handbag with a silk scarf, sunglasses and jewellery on marble',
    badge: 'Curated',
    objectPosition: '52% 58%',
  },
  {
    numeral: '08',
    name: 'Wellness',
    image: '/images/Home-Page-Cat-Images/Wellness_main_cat.png',
    alt: 'Person meditating cross-legged in a warm spa room with candles and towels',
    badge: 'Balance',
    objectPosition: '60% 48%',
  },
  {
    numeral: '09',
    name: 'Kitchen & Dining',
    image: '/images/Home-Page-Cat-Images/KitchenDining_main_cat.png',
    alt: 'Home cook plating a dish on a marble kitchen island at dusk',
    badge: 'Homeware',
    objectPosition: '55% 60%',
  },
];

export function CategorySection() {
  return (
    <section className="border-b border-ink-100 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
        <div className="text-center space-y-2">
          <p className="text-xs font-semibold uppercase tracking-caps text-accent-600">Discover</p>
          <h2 className="font-display text-display-md sm:text-display-lg font-bold tracking-display text-ink-900">
            Explore by Category
          </h2>
          <p className="mx-auto max-w-md text-sm text-ink-500">
            Nine premium worlds of shopping — one curated campaign.
          </p>
        </div>

        <div className="mt-8 grid grid-cols-2 gap-x-3 gap-y-5 sm:gap-x-5 sm:gap-y-8 lg:grid-cols-3 lg:gap-x-6 lg:gap-y-12">
          {categories.map((category, i) => (
            <div
              key={category.numeral}
              className="cat-reveal"
              style={{ animationDelay: `${i * 70}ms` }}
            >
              <CategoryCard {...category} />
            </div>
          ))}
        </div>

        <p className="mx-auto mt-8 max-w-xl text-center text-sm text-ink-500">
          Visual categories for browsing inspiration. Shopping functionality is not yet implemented
          — this section showcases our design vision.
        </p>
      </div>
    </section>
  );
}
