'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { getProduct, type Product } from '@/lib/api-client';
import { formatInr } from '@/lib/currency';

const COMPARE_KEY = 'shopsmart-compare-ids';

function readCompareIds(): string[] {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(COMPARE_KEY) || '[]');
    return Array.isArray(value)
      ? Array.from(new Set(value.filter((id): id is string => typeof id === 'string'))).slice(0, 3)
      : [];
  } catch {
    return [];
  }
}

function displayedValue(product: Product, label: string): string {
  if (label === 'Price') return formatInr(product.price);
  if (label === 'Availability') return product.stock_quantity > 0 ? 'In stock' : 'Out of stock';
  if (label === 'Brand') return product.brand || 'Not provided';
  const value = product.specifications?.[label];
  if (value === null || value === undefined || value === '') return 'Not provided';
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}

export function CompareExperience() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [unavailableIds, setUnavailableIds] = useState<string[]>([]);
  const [differencesOnly, setDifferencesOnly] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const ids = readCompareIds();
    setLoading(true);
    setError('');
    setUnavailableIds([]);
    Promise.allSettled(ids.map(getProduct))
      .then((results) => {
        if (cancelled) return;
        setProducts(
          results.flatMap((result) => (result.status === 'fulfilled' ? [result.value] : []))
        );
        const missing = ids.filter((_, index) => results[index].status === 'rejected');
        setUnavailableIds(missing);
        if (missing.length) {
          setError(
            'Some products are no longer available in the catalog. Remove them to continue comparing.'
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  useEffect(() => {
    const reload = () => setRefresh((value) => value + 1);
    window.addEventListener('shopsmart-compare', reload);
    return () => window.removeEventListener('shopsmart-compare', reload);
  }, []);

  const rows = useMemo(() => {
    const labels = [
      'Price',
      'Availability',
      'Brand',
      ...Array.from(
        new Set(
          products.flatMap((product) =>
            Object.keys(product.specifications || {}).filter((key) => !key.startsWith('_'))
          )
        )
      ),
    ];
    return labels
      .map((label) => ({
        label,
        values: products.map((product) => displayedValue(product, label)),
      }))
      .filter(({ values }) => !differencesOnly || new Set(values).size > 1);
  }, [differencesOnly, products]);

  function removeProduct(id: string) {
    const next = readCompareIds().filter((candidate) => candidate !== id);
    sessionStorage.setItem(COMPARE_KEY, JSON.stringify(next));
    window.dispatchEvent(new Event('shopsmart-compare'));
    setRefresh((value) => value + 1);
  }

  function clearComparison() {
    sessionStorage.removeItem(COMPARE_KEY);
    window.dispatchEvent(new Event('shopsmart-compare'));
    setProducts([]);
  }

  return (
    <section className="mx-auto max-w-7xl">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-ink-200 pb-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-700">
            Decision workspace
          </p>
          <h1 className="mt-2 font-display text-4xl font-semibold sm:text-5xl">
            Compare your shortlist
          </h1>
          <p className="mt-3 max-w-xl text-ink-600">
            Current product details are refreshed from the catalog each time you open this page.
          </p>
        </div>
        {products.length > 0 && (
          <button
            type="button"
            onClick={clearComparison}
            className="min-h-11 rounded-full border border-ink-300 px-5 text-sm font-semibold"
          >
            Clear shortlist
          </button>
        )}
      </div>

      {loading ? (
        <p role="status" className="rounded-2xl bg-white p-8">
          Refreshing selected products…
        </p>
      ) : error ? (
        <div role="alert" className="rounded-2xl border border-red-200 bg-white p-8">
          <p>{error}</p>
          <ul className="mt-3 space-y-2">
            {unavailableIds.map((id) => (
              <li key={id} className="flex flex-wrap items-center gap-3 text-sm">
                <span>Unavailable catalog product</span>
                <button
                  type="button"
                  onClick={() => removeProduct(id)}
                  className="min-h-11 underline"
                >
                  Remove product
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => setRefresh((value) => value + 1)}
            className="mt-4 min-h-11 underline"
          >
            Retry
          </button>
        </div>
      ) : products.length < 2 ? (
        <div className="rounded-2xl bg-white p-8 sm:p-12">
          <h2 className="font-display text-2xl font-semibold">Choose at least two products</h2>
          <p className="mt-2 text-ink-600">
            Use Compare on catalog items or product pages to build a shortlist of up to three.
          </p>
          <Link
            href="/products"
            className="mt-6 inline-flex min-h-11 items-center rounded-full bg-ink-900 px-6 font-semibold text-white"
          >
            Browse catalog
          </Link>
        </div>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-ink-600">
              {products.length} products · {rows.length} attributes
            </p>
            <label className="flex min-h-11 items-center gap-3 text-sm font-medium">
              <input
                type="checkbox"
                checked={differencesOnly}
                onChange={(event) => setDifferencesOnly(event.target.checked)}
                className="size-5 accent-ink-900"
              />
              Show differences only
            </label>
          </div>
          <p className="mb-2 text-xs text-ink-500 md:hidden">Swipe sideways to see each product.</p>
          <div className="max-h-[calc(100vh-18rem)] min-h-[18rem] overflow-auto rounded-2xl border border-ink-200 bg-white shadow-sm">
            <table className="w-full min-w-[720px] border-separate border-spacing-0 text-left text-sm">
              <caption className="sr-only">
                Live prices, availability and specifications for the products in your shortlist
              </caption>
              <thead>
                <tr>
                  <th className="sticky left-0 top-0 z-20 w-40 bg-[#f7f5f1] p-4 align-top">
                    Product facts
                  </th>
                  {products.map((product) => (
                    <th
                      key={product.id}
                      className="sticky top-0 z-10 min-w-56 border-l border-ink-100 bg-white p-4 align-top sm:min-w-64"
                    >
                      <div className="relative mx-auto mb-3 h-36 w-full max-w-48 overflow-hidden bg-[#f7f5f1]">
                        {product.image_url && (
                          <Image
                            src={product.image_url}
                            alt={product.image_alt || product.name}
                            fill
                            sizes="(max-width: 768px) 60vw, 240px"
                            className="object-contain p-3"
                          />
                        )}
                      </div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-accent-700">
                        {product.brand || 'Catalog product'}
                      </p>
                      <Link
                        href={`/products/${product.id}`}
                        className="mt-1 block font-display text-lg font-semibold leading-snug underline decoration-ink-300 underline-offset-4"
                      >
                        {product.name}
                      </Link>
                      <button
                        type="button"
                        onClick={() => removeProduct(product.id)}
                        className="mt-3 min-h-11 text-xs font-semibold text-ink-500 underline"
                      >
                        Remove
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map(({ label, values }) => {
                  const differs = new Set(values).size > 1;
                  return (
                    <tr key={label} className={`group ${differs ? 'bg-[#fbf7ef]' : ''}`}>
                      <th
                        scope="row"
                        className="sticky left-0 z-[1] border-t border-ink-100 bg-[#f7f5f1] p-4 font-semibold"
                      >
                        {label}
                      </th>
                      {values.map((value, index) => (
                        <td
                          key={`${products[index].id}-${label}`}
                          className={`border-l border-t border-ink-100 p-4 ${differs ? 'font-semibold text-ink-950' : 'text-ink-600'}`}
                        >
                          {value}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-ink-900 p-6 text-white sm:p-8">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/60">
                Want help interpreting the trade-offs?
              </p>
              <p className="mt-2 font-display text-xl">
                Ask ShopSmart to reason from these listed facts.
              </p>
            </div>
            <Link
              href={`/assistant?q=${encodeURIComponent(`Compare ${products.map((product) => product.name).join(' and ')} using only their listed specifications, price, and availability.`)}`}
              className="inline-flex min-h-11 items-center rounded-full bg-white px-6 font-semibold text-ink-900"
            >
              Ask AI about these
            </Link>
          </div>
        </>
      )}
    </section>
  );
}
