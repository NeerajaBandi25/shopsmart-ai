import type { HomepageData, ProductQuery } from '@/lib/api-client';

export function readCatalogQuery(
  params: Record<string, string | string[] | undefined>
): ProductQuery {
  const first = (key: string) => {
    const value = params[key];
    return Array.isArray(value) ? value[0] : value;
  };
  const money = (key: string) => {
    const value = first(key);
    return value && /^\d+$/.test(value) && Number.isSafeInteger(Number(value))
      ? Number(value)
      : undefined;
  };
  const sort = first('sort');
  return {
    q: first('q') || undefined,
    category: first('category') || undefined,
    brand: first('brand') || undefined,
    subcategory: first('subcategory') || undefined,
    min_price_minor: money('min_price_minor'),
    max_price_minor: money('max_price_minor'),
    in_stock_only: first('in_stock_only') === 'true' || undefined,
    sort:
      sort === 'price_asc' || sort === 'price_desc' || sort === 'name_asc' || sort === 'newest'
        ? sort
        : undefined,
  };
}

export function catalogUrl(filters: ProductQuery, skip: number): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '' && value !== false) params.set(key, String(value));
  });
  if (skip > 0) params.set('skip', String(skip));
  const query = params.toString();
  return '/products' + (query ? '?' + query : '');
}

/** Only explicit budget/category syntax is interpreted; prices and matches remain API facts. */
export function interpretCatalogSearch(
  filters: ProductQuery,
  categories: HomepageData['categories']
): ProductQuery {
  let query = filters.q?.trim() || '';
  const budget = query.match(
    /\b(?:under|below|up to|less than)\s*(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(k|lakh|lakhs)?\b/i
  );
  const next = { ...filters };
  if (budget) {
    const amount =
      Number(budget[1].replace(/,/g, '')) *
      (budget[2]?.toLowerCase() === 'k' ? 1000 : budget[2] ? 100000 : 1);
    if (Number.isSafeInteger(Math.round(amount * 100)) && amount > 0) {
      if (next.max_price_minor === undefined) next.max_price_minor = Math.round(amount * 100);
      query = query
        .replace(budget[0], '')
        .replace(/^(?:best|find|show me|a|an)\s+/i, '')
        .trim();
    }
  }
  const normalized = query.toLowerCase().replace(/_/g, ' ');
  const categoryMatches = categories
    .flatMap((item) => {
      const aliases = [item.label.toLowerCase(), item.value.replace(/_/g, ' ').toLowerCase()];
      return aliases
        .flatMap((alias) => [alias, alias.replace(/s$/, '')])
        .map((alias) => ({ item, alias }));
    })
    .sort((left, right) => right.alias.length - left.alias.length);
  const matched = categoryMatches.find(({ alias }) => {
    const at = normalized.indexOf(alias);
    return (
      at >= 0 &&
      (at === 0 || !/[a-z0-9]/.test(normalized[at - 1])) &&
      (at + alias.length === normalized.length || !/[a-z0-9]/.test(normalized[at + alias.length]))
    );
  });
  if (matched && !next.category) {
    next.category = matched.item.value;
    const at = normalized.indexOf(matched.alias);
    query = (query.slice(0, at) + query.slice(at + matched.alias.length))
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/^(?:for|a|an)\s+/i, '')
      .trim();
  }
  next.q = query || undefined;
  return next;
}
