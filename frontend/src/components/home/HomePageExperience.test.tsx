import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { getHomepage, getProducts, type Product, type HomepageData } from '@/lib/api-client';
import { HomePageExperience } from './HomePageExperience';

jest.mock('@/lib/api-client', () => ({ getHomepage: jest.fn(), getProducts: jest.fn() }));
jest.mock('./CatalogHero.module.css', () => ({}));
jest.mock('./HomeMerchandise.module.css', () => ({}));
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

function page(items: Product[]): HomepageData {
  return {
    categories: [
      { value: 'laptops', label: 'Laptops', count: 8 },
      { value: 'smartphones', label: 'Smartphones', count: 12 },
    ],
    featured: items,
    trending: [],
    recommendations: [],
    promotions: [],
  };
}

const mockedGetHomepage = jest.mocked(getHomepage);
const mockedGetProducts = jest.mocked(getProducts);

describe('homepage shopping experience', () => {
  beforeEach(() => {
    mockedGetHomepage.mockReset();
    mockedGetProducts.mockReset().mockResolvedValue({ items: [], skip: 0, limit: 100, total: 0 });
  });

  it('loads current catalog products and derives offer messaging from listed prices', async () => {
    mockedGetHomepage.mockResolvedValue(
      page([
        product,
        { ...product, id: 'product-2', name: 'Everyday Tote', list_price: null },
        { ...product, id: 'product-3', name: 'Unavailable Item', stock_quantity: 0 },
      ])
    );

    render(<HomePageExperience />);

    expect(mockedGetHomepage).toHaveBeenCalledWith();
    expect(await screen.findAllByRole('heading', { name: 'Canvas Weekender' })).toHaveLength(2);
    expect(screen.getByText('Listed offers')).toBeInTheDocument();
    expect(screen.getAllByText('Save ₹3.00')).toHaveLength(2);
    expect(screen.queryByRole('heading', { name: 'Unavailable Item' })).not.toBeInTheDocument();
    expect(screen.queryByText('Save ₹0.00')).not.toBeInTheDocument();
  });

  it('routes search and category links through supported product query parameters', async () => {
    mockedGetHomepage.mockResolvedValue(page([product]));
    render(<HomePageExperience />);

    fireEvent.click(await screen.findByRole('button', { name: 'Scene 2: Your brief' }));
    const search = screen.getByRole('searchbox', { name: 'What would you like to find?' });
    const searchForm = search.closest('form');
    expect(searchForm).toHaveAttribute('action', '/assistant');
    expect(searchForm).toHaveAttribute('method', 'get');
    expect(search).toHaveAttribute('name', 'q');
    expect(search).toHaveValue('Find laptops under ₹70,000');
    fireEvent.change(search, { target: { value: 'phone under 20k' } });
    expect(screen.getAllByText('Smartphones').length).toBeGreaterThan(0);
    expect(screen.getByRole('region', { name: 'Start with what matters.' })).toHaveTextContent(
      /20,000/
    );

    expect(await screen.findByRole('link', { name: /Laptops/ })).toHaveAttribute(
      'href',
      '/products?category=laptops'
    );
    expect(screen.getByRole('link', { name: /Smartphones/ })).toHaveAttribute(
      'href',
      '/products?category=smartphones'
    );
    expect(screen.getByRole('link', { name: 'Explore this brief' })).toHaveAttribute(
      'href',
      '/assistant?q=phone%20under%2020k'
    );
    await waitFor(() => expect(mockedGetHomepage).toHaveBeenCalledTimes(1));
  });

  it('walks the hero from real laptop candidates into a published-data comparison', async () => {
    mockedGetHomepage.mockResolvedValue(
      page([
        {
          ...product,
          id: 'laptop-1',
          name: 'Studybook',
          category: 'laptops',
          price: 4_899_900,
          specifications: { RAM: '16 GB RAM', Storage: '512 GB SSD' },
        },
        {
          ...product,
          id: 'laptop-2',
          name: 'Travelbook',
          category: 'laptops',
          price: 5_599_900,
          specifications: { RAM: '16 GB RAM', Storage: '1 TB SSD' },
        },
        {
          ...product,
          id: 'laptop-3',
          name: 'Workbook',
          category: 'laptops',
          price: 5_199_900,
          specifications: { RAM: '8 GB RAM', Storage: '512 GB SSD' },
        },
      ])
    );
    render(<HomePageExperience />);
    fireEvent.click(await screen.findByRole('button', { name: 'Scene 3: Explore' }));
    expect(screen.getByText('SHORTLISTED FROM AVAILABLE PRODUCTS')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Studybook' })[0]).toHaveAttribute(
      'href',
      '/products/laptop-1'
    );
    fireEvent.click(screen.getByRole('button', { name: 'Scene 4: Compare' }));
    expect(screen.getByRole('region', { name: 'Published product comparison' })).toHaveTextContent(
      '8 GB RAM'
    );
    fireEvent.click(screen.getByRole('button', { name: 'Scene 5: Decide' }));
    expect(
      screen.getByText('Lowest listed price among these in-stock options.')
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Scene 6: Purchase' }));
    expect(screen.getAllByText('Studybook').length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: 'Add to cart' }).length).toBeGreaterThan(0);
  });

  it('shows catalog errors with a working retry action', async () => {
    mockedGetHomepage.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(page([]));
    render(<HomePageExperience />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Current products could not be loaded.'
    );
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(mockedGetHomepage).toHaveBeenCalledTimes(2));
    expect(
      await screen.findByText('No in-stock products are listed at the moment.')
    ).toBeInTheDocument();
  });
});
