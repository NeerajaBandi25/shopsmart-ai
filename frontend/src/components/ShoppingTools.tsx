'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

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
  const [query, setQuery] = useState('');
  const [ids, setIds] = useState<string[]>([]);

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

  return (
    <>
      <button
        type="button"
        onClick={() => palette.current?.showModal()}
        className={`${pathname === '/' || pathname === '/compare' || pathname.startsWith('/products/') || pathname.startsWith('/assistant') ? 'hidden' : 'fixed bottom-5 right-5 z-30 hidden min-h-11 items-center gap-3 rounded-full bg-ink-900 px-5 py-3 text-sm font-semibold text-white shadow-lg focus-visible:ring-2 focus-visible:ring-accent-500 sm:flex'}`}
        aria-label="Open shopping commands"
      >
        Search & ask <kbd className="hidden text-xs text-white/70 sm:inline">Ctrl K</kbd>
      </button>
      {ids.length > 0 && pathname !== '/compare' && (
        <aside
          aria-label="Comparison tray"
          className="flex items-center justify-center border-b border-ink-200 bg-white px-4 py-1 sm:fixed sm:bottom-5 sm:left-4 sm:z-30 sm:max-w-[55vw] sm:rounded-full sm:border sm:py-3 sm:shadow-lg"
        >
          <Link href="/compare" className="min-h-11 py-3 text-sm font-semibold text-ink-900">
            Compare ({ids.length}/3)
          </Link>
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
    </>
  );
}
