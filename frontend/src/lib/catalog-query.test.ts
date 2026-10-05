import { catalogUrl, interpretCatalogSearch, readCatalogQuery } from './catalog-query';

const categories = [{ value: 'laptops', label: 'Laptops', count: 24 }];

describe('catalog query state', () => {
  it('turns an explicit INR budget and API category into authoritative search filters', () => {
    expect(interpretCatalogSearch({ q: 'Best laptop under ₹60,000' }, categories)).toEqual({
      q: undefined,
      category: 'laptops',
      max_price_minor: 6000000,
    });
    expect(interpretCatalogSearch({ q: 'laptop under 60k' }, categories)).toEqual({
      q: undefined,
      category: 'laptops',
      max_price_minor: 6000000,
    });
  });

  it('preserves explicit filters and unmatched search wording', () => {
    expect(
      interpretCatalogSearch({ q: 'camera under 30k', max_price_minor: 2000000 }, categories)
    ).toEqual({ q: 'camera', max_price_minor: 2000000 });
    expect(interpretCatalogSearch({ q: 'purple carryall' }, categories)).toEqual({
      q: 'purple carryall',
    });
  });

  it('round trips a shareable complete filter URL and ignores invalid numeric values', () => {
    const filters = {
      q: 'weekend bag',
      category: 'accessories',
      brand: 'Northstar',
      subcategory: 'carryall',
      min_price_minor: 10000,
      max_price_minor: 300000,
      in_stock_only: true,
      sort: 'price_asc' as const,
    };
    const url = catalogUrl(filters, 24);
    expect(url).toContain('skip=24');
    expect(readCatalogQuery(Object.fromEntries(new URLSearchParams(url.split('?')[1])))).toEqual(
      filters
    );
    expect(
      readCatalogQuery({ max_price_minor: '-1', min_price_minor: 'NaN', sort: 'invented' })
    ).toEqual(
      expect.objectContaining({
        max_price_minor: undefined,
        min_price_minor: undefined,
        sort: undefined,
      })
    );
  });
  it('extracts embedded category wording while preserving use-case intent', () => {
    expect(interpretCatalogSearch({ q: 'coding laptop under INR 70,000' }, categories)).toEqual({
      q: 'coding',
      category: 'laptops',
      max_price_minor: 7000000,
    });
    expect(interpretCatalogSearch({ q: 'laptop for coding under 70k' }, categories)).toEqual({
      q: 'coding',
      category: 'laptops',
      max_price_minor: 7000000,
    });
    expect(interpretCatalogSearch({ q: 'laptopcase' }, categories)).toEqual({ q: 'laptopcase' });
  });
});
