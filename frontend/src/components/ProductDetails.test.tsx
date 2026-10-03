import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { getProduct, getProducts, type Product, type ProductPage } from '@/lib/api-client';
import { ProductDetails } from '@/components/ProductDetails';
import { addCartItem } from '@/lib/cart-api';

const mockPush = jest.fn();

jest.mock('next/navigation', () => ({ useRouter: () => ({ push: mockPush }) }));
jest.mock('@/lib/api-client', () => ({ getProduct: jest.fn(), getProducts: jest.fn() }));
jest.mock('@/lib/cart-api', () => ({ addCartItem: jest.fn() }));

const mockedGetProduct = jest.mocked(getProduct);
const mockedGetProducts = jest.mocked(getProducts);
const mockedAddCartItem = jest.mocked(addCartItem);

const product: Product = {
  id: 'product-1',
  name: 'Northstar 14 Laptop',
  description: 'A portable laptop for everyday work.',
  category: 'laptops',
  brand: 'Northstar',
  sku: 'NORTHSTAR-14',
  price: 5_500_000,
  list_price: 6_000_000,
  image_url: null,
  image_alt: null,
  specifications: { Memory: '16 GB', Storage: '512 GB' },
  stock_quantity: 4,
  max_purchase_quantity: 2,
};

describe('ProductDetails', () => {
  beforeEach(() => {
    mockedGetProduct.mockReset();
    mockedGetProducts.mockReset();
    mockedGetProducts.mockResolvedValue({ items: [], skip: 0, limit: 8 } as ProductPage);
    mockedAddCartItem.mockReset();
    mockPush.mockReset();
  });

  it('renders product facts and discloses category photography fallback', async () => {
    mockedGetProduct.mockResolvedValue(product);

    render(<ProductDetails productId={product.id} />);

    expect(await screen.findByRole('heading', { name: product.name })).toBeInTheDocument();
    expect(screen.getAllByText('Northstar')).toHaveLength(2);
    expect(screen.getByText('₹55,000.00')).toBeInTheDocument();
    expect(screen.getByText('₹60,000.00')).toBeInTheDocument();
    expect(screen.getByText('8% off')).toBeInTheDocument();
    expect(screen.getByText('You save ₹5,000.00')).toBeInTheDocument();
    expect(screen.getByText('16 GB')).toBeInTheDocument();
    expect(screen.getByText('512 GB')).toBeInTheDocument();
    expect(
      screen.getByText(/delivery availability and timing have not been provided/i)
    ).toBeInTheDocument();
    expect(screen.getByText('Category image')).toBeInTheDocument();
    expect(screen.getByText(/product-specific image has not been supplied/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add to cart' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Buy now' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ask ShopSmart AI' })).toHaveAttribute(
      'href',
      '/assistant'
    );
    expect(screen.queryByText(/rating|reviews/i)).not.toBeInTheDocument();
  });

  it('adds the selected quantity to the cart and routes buy-now to checkout', async () => {
    mockedGetProduct.mockResolvedValue(product);
    mockedAddCartItem.mockResolvedValue({ items: [{ quantity: 2 }] } as never);

    render(<ProductDetails productId={product.id} />);
    await screen.findByRole('heading', { name: product.name });

    fireEvent.change(screen.getByRole('spinbutton', { name: 'Quantity' }), {
      target: { value: '2' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Buy now' }));

    await waitFor(() => expect(mockedAddCartItem).toHaveBeenCalledWith(product.id, 2));
    expect(mockPush).toHaveBeenCalledWith('/checkout');
  });

  it('compares only facts supplied by the current product contracts', async () => {
    const related = { ...product, id: 'product-2', name: 'Northstar 15 Laptop', price: 6_000_000 };
    mockedGetProduct.mockResolvedValue(product);
    mockedGetProducts.mockResolvedValue({ items: [product, related], skip: 0, limit: 8 });

    render(<ProductDetails productId={product.id} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Compare with this product' }));

    expect(screen.getByRole('heading', { name: 'Compare products' })).toBeInTheDocument();
    expect(screen.getByRole('table')).toHaveTextContent('Northstar 14 Laptop');
    expect(screen.getByRole('table')).toHaveTextContent('Northstar 15 Laptop');
    expect(screen.getByRole('table')).toHaveTextContent('16 GB');
  });

  it('does not show a markdown when list price is not greater than price', async () => {
    mockedGetProduct.mockResolvedValue({ ...product, list_price: product.price });

    render(<ProductDetails productId={product.id} />);

    await screen.findByRole('heading', { name: product.name });

    expect(screen.queryByText(/% off/)).not.toBeInTheDocument();
    expect(screen.queryByText(/you save/i)).not.toBeInTheDocument();
  });

  it('opens and closes the product image viewer', async () => {
    mockedGetProduct.mockResolvedValue({
      ...product,
      image_url: '/images/products/northstar-14.jpg',
      image_alt: 'Northstar 14 open on a desk',
    });

    render(<ProductDetails productId={product.id} />);
    await screen.findByRole('heading', { name: product.name });

    fireEvent.click(screen.getByRole('button', { name: 'Expand product image' }));
    expect(screen.getByRole('dialog', { name: `${product.name} image` })).toBeInTheDocument();
    expect(screen.getAllByRole('img', { name: 'Northstar 14 open on a desk' })).toHaveLength(2);

    fireEvent.click(screen.getByRole('button', { name: 'Close image' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders an actionable unavailable state when the product lookup fails', async () => {
    mockedGetProduct.mockRejectedValue(new Error('Product not found'));

    render(<ProductDetails productId="missing-product" />);

    expect(await screen.findByRole('heading', { name: 'Product unavailable' })).toBeInTheDocument();
    expect(screen.getByText('This product is no longer available.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to products' })).toHaveAttribute(
      'href',
      '/products'
    );
  });

  it('does not use unrelated category photography when the product category is unknown', async () => {
    mockedGetProduct.mockResolvedValue({ ...product, category: null });

    render(<ProductDetails productId={product.id} />);

    expect(
      await screen.findByRole('img', { name: 'Product image unavailable' })
    ).toBeInTheDocument();
    expect(screen.queryByText('Category image')).not.toBeInTheDocument();
  });
});
