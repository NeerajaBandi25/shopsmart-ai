'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { getProduct, type Product } from '@/lib/api-client';
import { formatInr } from '@/lib/currency';

const COMPARE_KEY = 'shopsmart-compare-ids';

export function CompareButton({ productId }: { productId: string }) {
  const [selected, setSelected] = useState(false);
  useEffect(() => {
    const refresh = () => setSelected(readCompareIds().includes(productId));
    refresh();
    window.addEventListener('shopsmart-compare', refresh);
    return () => window.removeEventListener('shopsmart-compare', refresh);
  }, [productId]);
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={() => {
        const ids = readCompareIds();
        const next = selected
          ? ids.filter((id) => id !== productId)
          : [...ids, productId].slice(-3);
        sessionStorage.setItem(COMPARE_KEY, JSON.stringify(next));
        window.dispatchEvent(new Event('shopsmart-compare'));
      }}
      className="min-h-11 rounded-sm border border-ink-300 px-4 text-sm font-semibold text-ink-800 focus-visible:ring-2 focus-visible:ring-accent-500"
    >
      {selected ? 'Remove from compare' : 'Compare'}
    </button>
  );
}

function readCompareIds(): string[] {
  try {
    const ids: unknown = JSON.parse(sessionStorage.getItem(COMPARE_KEY) || '[]');
    return Array.isArray(ids)
      ? ids.filter((id): id is string => typeof id === 'string').slice(0, 3)
      : [];
  } catch {
    return [];
  }
}

export function ShoppingTools() {
  const pathname = usePathname();
  const palette = useRef<HTMLDialogElement>(null);
  const comparison = useRef<HTMLDialogElement>(null);
  const [query, setQuery] = useState('');
  const [ids, setIds] = useState<string[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const refresh = () => setIds(readCompareIds());
    const shortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        palette.current?.showModal();
      }
    };
    const openCommands = () => palette.current?.showModal();
    refresh();
    window.addEventListener('shopsmart-compare', refresh);
    window.addEventListener('keydown', shortcut);
    window.addEventListener('shopsmart-commands', openCommands);
    return () => {
      window.removeEventListener('shopsmart-compare', refresh);
      window.removeEventListener('keydown', shortcut);
      window.removeEventListener('shopsmart-commands', openCommands);
    };
  }, []);

  async function openComparison() {
    comparison.current?.showModal();
    setLoading(true);
    setError('');
    try {
      // Persist IDs only. Refresh authoritative facts when reopening comparison
      // so navigation cannot turn cached browser prices into commerce authority.
      setProducts(await Promise.all(ids.map(getProduct)));
    } catch {
      setError('A selected product is unavailable. Remove it and try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => palette.current?.showModal()}
        className={`${pathname === '/' || pathname.startsWith('/products/') || pathname.startsWith('/assistant') ? 'hidden' : 'fixed bottom-5 right-5 z-30 hidden min-h-11 items-center gap-3 rounded-full bg-ink-900 px-5 py-3 text-sm font-semibold text-white shadow-lg focus-visible:ring-2 focus-visible:ring-accent-500 sm:flex'}`}
        aria-label="Open shopping commands"
      >
        Search & ask <kbd className="hidden text-xs text-white/70 sm:inline">Ctrl K</kbd>
      </button>
      {ids.length > 0 && (
        <aside
          aria-label="Comparison tray"
          className="flex items-center justify-center border-b border-ink-200 bg-white px-4 py-1 sm:fixed sm:bottom-5 sm:left-4 sm:z-30 sm:max-w-[55vw] sm:rounded-full sm:border sm:py-3 sm:shadow-lg"
        >
          <button
            type="button"
            onClick={openComparison}
            className="min-h-11 text-sm font-semibold text-ink-900"
          >
            Compare ({ids.length}/3)
          </button>
          <button
            type="button"
            aria-label="Clear comparison"
            onClick={() => {
              sessionStorage.removeItem(COMPARE_KEY);
              window.dispatchEvent(new Event('shopsmart-compare'));
            }}
            className="ml-3 min-h-11 text-sm text-ink-500"
          >
            Clear
          </button>
        </aside>
      )}
      <dialog
        ref={palette}
        aria-labelledby="shopping-command-title"
        className="w-[calc(100%-2rem)] max-w-xl rounded-2xl border border-ink-200 bg-white p-6 text-ink-900 shadow-2xl backdrop:bg-ink-950/60"
      >
        <div className="flex items-center justify-between gap-4">
          <h2 id="shopping-command-title" className="font-display text-2xl font-bold">
            What are you looking for?
          </h2>
          <button
            type="button"
            onClick={() => palette.current?.close()}
            className="min-h-11 px-2"
            aria-label="Close shopping commands"
          >
            Close
          </button>
        </div>
        <label className="mt-5 block text-sm">
          Search or describe your ideal product
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            type="search"
            className="mt-2 h-12 w-full rounded-lg border border-ink-300 px-3"
            placeholder="A laptop for coding under ₹70,000"
          />
        </label>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            onClick={() => palette.current?.close()}
            href={`/products?q=${encodeURIComponent(query)}`}
            className="rounded-full bg-ink-900 px-5 py-3 text-sm font-semibold text-white"
          >
            Search catalog
          </Link>
          <Link
            onClick={() => palette.current?.close()}
            href={`/assistant?q=${encodeURIComponent(query)}`}
            className="rounded-full border border-ink-300 px-5 py-3 text-sm font-semibold"
          >
            Ask shopping AI
          </Link>
        </div>
        <p className="mt-5 text-xs text-ink-500">
          Press Escape to close. Product facts and cart totals come from the store.
        </p>
      </dialog>
      <dialog
        ref={comparison}
        aria-labelledby="comparison-title"
        className="w-[calc(100%-2rem)] max-w-5xl rounded-2xl border border-ink-200 bg-white p-5 text-ink-900 shadow-2xl backdrop:bg-ink-950/60"
      >
        <div className="flex items-center justify-between gap-4">
          <h2 id="comparison-title" className="font-display text-2xl font-bold">
            Your shortlist
          </h2>
          <button
            type="button"
            onClick={() => comparison.current?.close()}
            className="min-h-11 px-2"
          >
            Close comparison
          </button>
        </div>
        {loading ? (
          <p role="status" className="py-8">
            Refreshing product details…
          </p>
        ) : error ? (
          <p role="alert" className="py-8">
            {error}
          </p>
        ) : (
          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[500px] text-left text-sm">
              <caption className="sr-only">
                Current prices, stock and specifications for your selected products
              </caption>
              <thead>
                <tr>
                  <th className="p-3">Product</th>
                  {products.map((product) => (
                    <th key={product.id} className="p-3">
                      <Link
                        href={`/products/${product.id}`}
                        onClick={() => comparison.current?.close()}
                        className="underline"
                      >
                        {product.name}
                      </Link>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  'Price',
                  'Availability',
                  ...Array.from(
                    new Set(
                      products.flatMap((product) =>
                        Object.keys(product.specifications || {}).filter(
                          (key) => !key.startsWith('_')
                        )
                      )
                    )
                  ),
                ].map((label) => (
                  <tr key={label} className="border-t border-ink-100">
                    <th scope="row" className="p-3 font-medium">
                      {label}
                    </th>
                    {products.map((product) => (
                      <td key={product.id} className="p-3">
                        {label === 'Price'
                          ? formatInr(product.price)
                          : label === 'Availability'
                            ? product.stock_quantity > 0
                              ? 'In stock'
                              : 'Out of stock'
                            : String(product.specifications?.[label] ?? 'Not provided')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </dialog>
    </>
  );
}
