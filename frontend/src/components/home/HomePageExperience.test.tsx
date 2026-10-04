import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { ImgHTMLAttributes } from 'react';
import {
  getHeroStory,
  getHomepage,
  type HeroStoryData,
  type HomepageData,
  type Product,
} from '@/lib/api-client';
import { getCart, type Cart } from '@/lib/cart-api';
import { useCommerceStore } from '@/lib/commerce-store';
import { HomePageExperience } from './HomePageExperience';

jest.mock('@/lib/api-client', () => ({ getHomepage: jest.fn(), getHeroStory: jest.fn() }));
jest.mock('@/lib/cart-api', () => ({
  getCart: jest.fn(),
  addCartItem: jest.fn(),
  applyCartCoupon: jest.fn(),
}));
jest.mock('./CatalogHero.module.css', () => ({}));
jest.mock('./HomeMerchandise.module.css', () => ({}));
jest.mock('@/components/AddToCartButton', () => ({
  AddToCartButton: () => <button type="button">Add to cart</button>,
}));
jest.mock('next/image', () => ({
  __esModule: true,
  default: ({
    fill,
    priority,
    ...props
  }: ImgHTMLAttributes<HTMLImageElement> & { fill?: boolean; priority?: boolean }) => {
    void fill;
    void priority;
    // eslint-disable-next-line @next/next/no-img-element -- lightweight mock for Next Image.
    return <img {...props} alt={props.alt ?? ''} />;
  },
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

const candidates: Product[] = [
  {
    ...product,
    id: 'laptop-1',
    name: 'Studybook',
    category: 'laptops',
    brand: 'Vellune',
    sku: 'LAPTOP-1',
    price: 5_549_000,
    image_url: '/images/products/portfolio/laptops/01.jpg',
    image_alt: 'Studio laptop photograph',
    specifications: { RAM: '16 GB RAM', Processor: '8-core processor', Storage: '512 GB SSD' },
  },
  {
    ...product,
    id: 'laptop-2',
    name: 'Officebook',
    category: 'laptops',
    brand: 'Vellune',
    sku: 'LAPTOP-2',
    price: 5_849_000,
    image_url: '/images/products/portfolio/laptops/02.jpg',
    image_alt: 'Studio office laptop photograph',
    specifications: {
      RAM: '16 GB RAM',
      Processor: '8-core processor',
      Graphics: 'Integrated graphics',
    },
  },
  {
    ...product,
    id: 'laptop-3',
    name: 'Featherweight',
    category: 'laptops',
    brand: 'Merroway',
    sku: 'LAPTOP-3',
    price: 6_249_000,
    image_url: '/images/products/portfolio/laptops/03.jpg',
    image_alt: 'Studio travel laptop photograph',
    specifications: { RAM: '16 GB RAM', Processor: '8-core processor', Storage: '1 TB SSD' },
  },
];

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

function heroStory(): HeroStoryData {
  return {
    query: 'Best laptop for coding and local AI under ₹70,000',
    budget_minor: 7_000_000,
    candidates,
    recommended_product_id: 'laptop-1',
    recommendation: 'Best fit in this shortlist: 16 GB RAM at the lowest listed price.',
    evidence: [
      { label: 'Memory', value: '16 GB RAM' },
      { label: 'Processor', value: '8-core processor' },
      { label: 'Price', value: '₹55,490' },
      { label: 'Below budget', value: '₹14,510' },
    ],
    savings_minor: 1_451_000,
  };
}

const mockedGetHomepage = jest.mocked(getHomepage);
const mockedGetHeroStory = jest.mocked(getHeroStory);
const mockedGetCart = jest.mocked(getCart);

const emptyCart: Cart = {
  items: [],
  subtotal: 0,
  currency: 'INR',
  coupon_code: null,
  coupon_evaluation: null,
  applied_promotions: [],
  discount_total_cents: 0,
  total_cents: 0,
};

describe('homepage shopping experience', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: jest.fn().mockReturnValue({
        matches: false,
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
      }),
    });
    mockedGetHomepage.mockReset();
    mockedGetHeroStory.mockReset().mockResolvedValue(heroStory());
    mockedGetCart.mockReset().mockResolvedValue(emptyCart);
    useCommerceStore.getState().clearPrivateCommerce();
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
    expect(mockedGetHeroStory).toHaveBeenCalledWith();
    expect(await screen.findAllByRole('heading', { name: 'Canvas Weekender' })).toHaveLength(2);
    expect(screen.getByText('Listed offers')).toBeInTheDocument();
    expect(screen.getAllByText('Save ₹3.00')).toHaveLength(2);
    expect(screen.queryByRole('heading', { name: 'Unavailable Item' })).not.toBeInTheDocument();
    expect(screen.queryByText('Save ₹0.00')).not.toBeInTheDocument();
  });

  it('presents the backend shortlist, published evidence, and linked product identities', async () => {
    mockedGetHomepage.mockResolvedValue(page([product]));
    const { container } = render(<HomePageExperience />);

    expect(await screen.findAllByRole('heading', { name: 'ASK BETTER. BUY BETTER.' })).toHaveLength(
      2
    );
    expect(screen.getAllByText(heroStory().query)).toHaveLength(2);
    expect(screen.getByText('16 GB+')).toBeInTheDocument();
    expect(screen.getByText(/SHOPSMART ANALYSIS/)).toBeInTheDocument();
    expect(screen.getByText(heroStory().recommendation)).toBeInTheDocument();
    expect(container.querySelector('a[href="/products/laptop-1"]')).toBeInTheDocument();
    const imageSources = Array.from(
      container.querySelectorAll<HTMLImageElement>(
        'img[src^="/images/products/portfolio/laptops/"]'
      )
    ).map((image) => image.getAttribute('src'));
    expect(new Set(imageSources).size).toBe(3);
    expect(screen.getByRole('button', { name: 'Go to Ask scene' })).toHaveAttribute(
      'aria-current',
      'step'
    );
    await waitFor(() => expect(mockedGetHeroStory).toHaveBeenCalledTimes(1));
  });

  it('restores the signed-in cart and eligible coupon in the hero after reload', async () => {
    const homepage = page([product]);
    homepage.promotions = [
      {
        name: 'Laptop discovery offer',
        description: null,
        discount_type: 'percentage',
        discount_value: 5,
        ends_at: '2026-11-02T17:21:09.946877Z',
        scope_category: 'laptops',
      },
    ];
    mockedGetHomepage.mockResolvedValue(homepage);
    mockedGetCart.mockResolvedValue({
      ...emptyCart,
      items: [
        {
          product_id: 'laptop-1',
          name: 'Studybook',
          sku: 'LAPTOP-1',
          image_url: candidates[0].image_url,
          image_alt: candidates[0].image_alt,
          unit_price: candidates[0].price,
          quantity: 2,
          line_total: candidates[0].price * 2,
          stock_quantity: 63,
          max_purchase_quantity: 5,
        },
      ],
      subtotal: candidates[0].price * 2,
      coupon_code: 'SAVE20',
      coupon_evaluation: {
        promotion_id: 'promotion-1',
        code: 'SAVE20',
        name: 'Welcome savings',
        eligible: true,
        reason_code: 'eligible',
        discount_cents: 2_219_600,
        applied_scope: { type: 'all' },
      },
      discount_total_cents: 2_219_600,
      total_cents: candidates[0].price * 2 - 2_219_600,
    });
    render(<HomePageExperience hasSession />);

    const cartLink = await screen.findByRole('link', { name: 'View cart' });
    expect(cartLink).toHaveTextContent('2');
    expect(await screen.findByRole('button', { name: /ADDED TO CART/ })).toBeEnabled();
    await waitFor(() => expect(document.querySelector('#hero-offer-code')).not.toBeNull());
    expect(document.querySelector<HTMLInputElement>('#hero-offer-code')).toHaveValue('SAVE20');
    expect(document.body).toHaveTextContent(/SAVE20 applied/);
    expect(document.body).toHaveTextContent(/CART VERIFIED/);
  });

  it('keeps ordinary catalog category navigation available below the guided story', async () => {
    mockedGetHomepage.mockResolvedValue(page([product]));
    render(<HomePageExperience />);

    const categoryNavigation = await screen.findByRole('navigation', {
      name: 'Product categories',
    });
    expect(
      await within(categoryNavigation).findByRole('link', { name: /Laptops/ })
    ).toHaveAttribute('href', '/products?category=laptops');
    expect(
      await within(categoryNavigation).findByRole('link', { name: /Smartphones/ })
    ).toHaveAttribute('href', '/products?category=smartphones');
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
