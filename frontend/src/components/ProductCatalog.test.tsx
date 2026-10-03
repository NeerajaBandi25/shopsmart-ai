import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { getHomepage, getProducts, type ProductPage } from '@/lib/api-client';
import { ProductCatalog } from '@/components/ProductCatalog';

jest.mock('@/lib/api-client', () => ({
  getProducts: jest.fn(),
  getHomepage: jest.fn(),
}));
jest.mock('@/lib/cart-api', () => ({ addCartItem: jest.fn() }));

const mockedGetProducts = jest.mocked(getProducts);

const product = {
  id: '00000000-0000-0000-0000-000000000001',
  name: 'Canvas Weekender',
  description: 'A durable carryall for short trips.',
  category: 'accessories',
  brand: 'Northstar Goods',
  sku: 'BAG-001',
  price: 1299,
  list_price: null,
  image_url: null,
  image_alt: null,
  specifications: null,
  stock_quantity: 8,
  max_purchase_quantity: 3,
};

function page(items: ProductPage['items'], skip = 0, total = items.length + skip): ProductPage {
  return { items, skip, limit: 24, total };
}

describe('ProductCatalog', () => {
  beforeEach(() => {
    mockedGetProducts.mockReset();
    jest.mocked(getHomepage).mockResolvedValue({
      categories: [{ value: 'laptops', label: 'Laptops', count: 8 }],
      featured: [],
      trending: [],
      recommendations: [],
      promotions: [],
    });
    window.history.replaceState(null, '', '/products');
  });

  it('shows a loading state while products are being requested', () => {
    mockedGetProducts.mockImplementation(() => new Promise(() => undefined));

    jest.mocked(getHomepage).mockImplementation(() => new Promise(() => undefined));
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
    expect(screen.getByText('₹12.99')).toBeInTheDocument();
    expect(screen.getByText('8 in stock')).toBeInTheDocument();
    expect(screen.getByText('Out of stock', { selector: 'p' })).toBeInTheDocument();
    expect(screen.getByText('A durable carryall for short trips.')).toBeInTheDocument();
    expect(mockedGetProducts).toHaveBeenCalledWith(0, 24, {});
    expect(screen.getByRole('button', { name: 'Add to cart' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View cart' })).toHaveAttribute('href', '/cart');
    expect(screen.getByRole('link', { name: 'View Canvas Weekender details' })).toHaveAttribute(
      'href',
      `/products/${product.id}`
    );
    expect(screen.getAllByRole('img', { name: 'Product image unavailable' })).toHaveLength(2);
  });

  it('shows an empty state when the API returns no products', async () => {
    mockedGetProducts.mockResolvedValue(page([]));

    render(<ProductCatalog />);

    expect(await screen.findByText('No products match these filters.')).toBeInTheDocument();
  });

  it('does not assign category photography when a product category is unknown', async () => {
    mockedGetProducts.mockResolvedValue(page([{ ...product, category: null }]));

    render(<ProductCatalog />);

    expect(
      await screen.findByRole('img', { name: 'Product image unavailable' })
    ).toBeInTheDocument();
    expect(screen.queryByText('Category image')).not.toBeInTheDocument();
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
      .mockResolvedValueOnce(page(fullPage, 0, 25))
      .mockResolvedValueOnce(page([{ ...product, id: 'page-two' }], 24));

    render(<ProductCatalog />);

    fireEvent.click(await screen.findByRole('button', { name: 'Next' }));

    await waitFor(() => expect(mockedGetProducts).toHaveBeenLastCalledWith(24, 24, {}));
    expect(await screen.findByRole('heading', { name: 'Canvas Weekender' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled();
  });

  it('shows a lower-bound count and keeps paging when a legacy API omits total', async () => {
    const fullPage = Array.from({ length: 24 }, (_, index) => ({
      ...product,
      id: `00000000-0000-0000-0000-${String(index + 1).padStart(12, '0')}`,
    }));
    mockedGetProducts.mockResolvedValue({ items: fullPage, skip: 0, limit: 24 } as ProductPage);

    render(<ProductCatalog />);

    expect(await screen.findByText('24+ products')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled();
  });

  it('applies search, category, brand, subcategory, price, stock, and sort filters', async () => {
    mockedGetProducts.mockResolvedValue(page([product]));
    render(<ProductCatalog />);

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search products' }), {
      target: { value: 'laptop' },
    });
    await screen.findByRole('option', { name: 'Laptops' });
    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'laptops' } });
    fireEvent.change(screen.getByRole('searchbox', { name: 'Brand' }), {
      target: { value: 'Northstar' },
    });
    fireEvent.change(screen.getByRole('searchbox', { name: 'Subcategory' }), {
      target: { value: 'student notebooks' },
    });
    fireEvent.change(screen.getByLabelText('Maximum price (₹)'), { target: { value: '60000' } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'In stock' }));
    fireEvent.change(screen.getByLabelText('Sort by'), { target: { value: 'price_asc' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() =>
      expect(mockedGetProducts).toHaveBeenLastCalledWith(0, 24, {
        q: 'laptop',
        category: 'laptops',
        brand: 'Northstar',
        subcategory: 'student notebooks',
        max_price_minor: 6000000,
        in_stock_only: true,
        sort: 'price_asc',
      })
    );
  });
  it('hydrates full shareable filters and restores browser history', async () => {
    mockedGetProducts.mockResolvedValue(page([product]));
    render(
      <ProductCatalog
        initialFilters={{
          category: 'laptops',
          max_price_minor: 6000000,
          min_price_minor: 3000000,
          brand: 'Northstar',
          subcategory: 'notebooks',
          in_stock_only: true,
          sort: 'price_asc',
        }}
        initialSkip={24}
      />
    );
    await screen.findByRole('heading', { name: 'Canvas Weekender' });
    expect(mockedGetProducts).toHaveBeenCalledWith(
      24,
      24,
      expect.objectContaining({
        category: 'laptops',
        max_price_minor: 6000000,
        min_price_minor: 3000000,
        sort: 'price_asc',
      })
    );
    expect(screen.getByLabelText('Minimum price (₹)')).toHaveValue(30000);
    expect(screen.getByLabelText('Maximum price (₹)')).toHaveValue(60000);
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect(window.location.search).toBe('');
    window.history.replaceState(null, '', '/products?category=laptops&max_price_minor=4000000');
    fireEvent(window, new PopStateEvent('popstate'));
    await waitFor(() =>
      expect(mockedGetProducts).toHaveBeenLastCalledWith(
        0,
        24,
        expect.objectContaining({ category: 'laptops', max_price_minor: 4000000 })
      )
    );
    expect(screen.getByLabelText('Maximum price (₹)')).toHaveValue(40000);
  });

  it('rejects reversed price ranges before requesting products', async () => {
    mockedGetProducts.mockResolvedValue(page([product]));
    render(<ProductCatalog />);
    await screen.findByRole('heading', { name: 'Canvas Weekender' });
    fireEvent.change(screen.getByLabelText('Minimum price (₹)'), { target: { value: '2000' } });
    fireEvent.change(screen.getByLabelText('Maximum price (₹)'), { target: { value: '1000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid price range');
    expect(mockedGetProducts).toHaveBeenCalledTimes(1);
  });
});
