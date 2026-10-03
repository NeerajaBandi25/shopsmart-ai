import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { getProducts, type Product, type ProductPage } from '@/lib/api-client';
import { HomePageExperience } from './HomePageExperience';

jest.mock('@/lib/api-client', () => ({ getProducts: jest.fn() }));
jest.mock('@/components/AddToCartButton', () => ({
  AddToCartButton: () => <button type="button">Add to cart</button>,
}));

const product: Product = {
  id: 'product-1',
  name: 'Canvas Weekender',
  description: 'A carryall for short trips.',
  category: 'accessories',
  brand: 'Northstar Goods',
  sku: 'BAG-001',
  price: 1299,
  list_price: 1599,
  image_url: null,
  image_alt: null,
  specifications: null,
  stock_quantity: 8,
  max_purchase_quantity: 3,
};

function page(items: Product[]): ProductPage {
  return { items, skip: 0, limit: 24, total: items.length };
}

const mockedGetProducts = jest.mocked(getProducts);

describe('homepage shopping experience', () => {
  beforeEach(() => {
    mockedGetProducts.mockReset();
  });

  it('loads current catalog products and derives offer messaging from listed prices', async () => {
    mockedGetProducts.mockResolvedValue(
      page([
        product,
        { ...product, id: 'product-2', name: 'Everyday Tote', list_price: null },
        { ...product, id: 'product-3', name: 'Unavailable Item', stock_quantity: 0 },
      ])
    );

    render(<HomePageExperience />);

    expect(mockedGetProducts).toHaveBeenCalledWith(0, 24, { sort: 'newest' });
    expect(await screen.findAllByRole('heading', { name: 'Canvas Weekender' })).toHaveLength(2);
    expect(screen.getByText('Listed offers')).toBeInTheDocument();
    expect(screen.getAllByText('Save ₹3.00')).toHaveLength(2);
    expect(screen.queryByRole('heading', { name: 'Unavailable Item' })).not.toBeInTheDocument();
    expect(screen.queryByText('Save ₹0.00')).not.toBeInTheDocument();
  });

  it('routes search and category links through supported product query parameters', async () => {
    mockedGetProducts.mockResolvedValue(page([product]));
    render(<HomePageExperience />);

    const search = screen.getByRole('searchbox', { name: 'Search products' });
    fireEvent.change(search, { target: { value: 'travel bag' } });
    const searchForm = search.closest('form');
    expect(searchForm).toHaveAttribute('action', '/products');
    expect(searchForm).toHaveAttribute('method', 'get');
    expect(search).toHaveAttribute('name', 'q');

    expect(screen.getByRole('link', { name: /Laptops/ })).toHaveAttribute(
      'href',
      '/products?category=laptops'
    );
    expect(screen.getByRole('link', { name: /Smartphones/ })).toHaveAttribute(
      'href',
      '/products?category=smartphones'
    );
    expect(screen.getByRole('link', { name: 'Ask the shopping assistant' })).toHaveAttribute(
      'href',
      '/assistant'
    );
    await waitFor(() => expect(mockedGetProducts).toHaveBeenCalledTimes(1));
  });

  it('shows catalog errors with a working retry action', async () => {
    mockedGetProducts.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(page([]));
    render(<HomePageExperience />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Current products could not be loaded.'
    );
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(mockedGetProducts).toHaveBeenCalledTimes(2));
    expect(
      await screen.findByText('No in-stock products are listed at the moment.')
    ).toBeInTheDocument();
  });
});
