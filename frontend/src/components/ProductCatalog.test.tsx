import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { getProducts, type ProductPage } from '@/lib/api-client';
import { ProductCatalog } from '@/components/ProductCatalog';

jest.mock('@/lib/api-client', () => ({
  getProducts: jest.fn(),
}));

const mockedGetProducts = jest.mocked(getProducts);

const product = {
  id: '00000000-0000-0000-0000-000000000001',
  name: 'Canvas Weekender',
  description: 'A durable carryall for short trips.',
  sku: 'BAG-001',
  price: 1299,
  stock_quantity: 8,
  max_purchase_quantity: 3,
};

function page(items: ProductPage['items'], skip = 0): ProductPage {
  return { items, skip, limit: 24 };
}

describe('ProductCatalog', () => {
  beforeEach(() => {
    mockedGetProducts.mockReset();
  });

  it('shows a loading state while products are being requested', () => {
    mockedGetProducts.mockImplementation(() => new Promise(() => undefined));

    render(<ProductCatalog />);

    expect(screen.getByRole('status')).toHaveTextContent('Loading products...');
  });

  it('renders API products, price, and stock availability', async () => {
    mockedGetProducts.mockResolvedValue(
      page([
        product,
        {
          ...product,
          id: 'out-of-stock',
          name: 'Out of stock item',
          description: null,
          sku: 'EMPTY-001',
          price: 500,
          stock_quantity: 0,
        },
      ])
    );

    render(<ProductCatalog />);

    expect(await screen.findByRole('heading', { name: 'Canvas Weekender' })).toBeInTheDocument();
    expect(screen.getByText('$12.99')).toBeInTheDocument();
    expect(screen.getByText('8 in stock')).toBeInTheDocument();
    expect(screen.getByText('Out of stock')).toBeInTheDocument();
    expect(screen.getByText('A durable carryall for short trips.')).toBeInTheDocument();
    expect(mockedGetProducts).toHaveBeenCalledWith(0, 24);
  });

  it('shows an empty state when the API returns no products', async () => {
    mockedGetProducts.mockResolvedValue(page([]));

    render(<ProductCatalog />);

    expect(await screen.findByText('No products are available yet.')).toBeInTheDocument();
  });

  it('shows request failures and retries the current page', async () => {
    mockedGetProducts
      .mockRejectedValueOnce(new Error('Catalog service unavailable'))
      .mockResolvedValueOnce(page([product]));

    render(<ProductCatalog />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Catalog service unavailable');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));

    await waitFor(() => expect(mockedGetProducts).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole('heading', { name: 'Canvas Weekender' })).toBeInTheDocument();
  });

  it('moves between API pages', async () => {
    const fullPage = Array.from({ length: 24 }, (_, index) => ({
      ...product,
      id: `00000000-0000-0000-0000-${String(index + 1).padStart(12, '0')}`,
    }));
    mockedGetProducts
      .mockResolvedValueOnce(page(fullPage))
      .mockResolvedValueOnce(page([{ ...product, id: 'page-two' }], 24));

    render(<ProductCatalog />);

    fireEvent.click(await screen.findByRole('button', { name: 'Next' }));

    await waitFor(() => expect(mockedGetProducts).toHaveBeenLastCalledWith(24, 24));
    expect(await screen.findByRole('heading', { name: 'Canvas Weekender' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled();
  });
});
