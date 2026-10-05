import { fireEvent, render, screen, within } from '@testing-library/react';
import CommerceResults, { ProductResult } from './CommerceResults';

it('keeps a compact shortlist and exposes every authoritative result on request', () => {
  const products: ProductResult[] = Array.from({ length: 7 }, (_, index) => ({
    id: `record-${index}`,
    name: `Catalog configuration ${index}`,
    description: null,
    sku: `SKU-${index}`,
    price_cents: 10000 + index,
    stock_quantity: 2,
  }));
  const onAddToCart = jest.fn();
  const onCompare = jest.fn();
  render(
    <CommerceResults
      resultId="result-1"
      products={products}
      addingProductId={null}
      cartAction={null}
      onAddToCart={onAddToCart}
      onCompare={onCompare}
    />
  );

  expect(screen.getAllByRole('article')).toHaveLength(4);
  expect(screen.getByText('Showing 4 of 7 catalog results')).toBeInTheDocument();
  expect(
    screen.queryByRole('heading', { name: 'Catalog configuration 6' })
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Compare the first two' }));
  expect(onCompare).toHaveBeenCalledTimes(1);

  const expand = screen.getByRole('button', { name: 'Show 3 more products' });
  expect(expand).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(expand);
  expect(screen.getAllByRole('article')).toHaveLength(7);
  expect(screen.getByText('Showing 7 of 7 catalog results')).toBeInTheDocument();
  const finalCard = screen
    .getByRole('heading', { name: 'Catalog configuration 6' })
    .closest('article')!;
  fireEvent.click(within(finalCard).getByRole('button', { name: 'Add to cart' }));
  expect(onAddToCart).toHaveBeenCalledWith('record-6', 'result-1');

  const collapse = screen.getByRole('button', { name: 'Show fewer products' });
  expect(collapse).toHaveAttribute('aria-expanded', 'true');
  fireEvent.click(collapse);
  expect(screen.getAllByRole('article')).toHaveLength(4);
});
