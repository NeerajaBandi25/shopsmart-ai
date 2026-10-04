import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { CompareExperience } from './CompareExperience';
import { getProduct } from '@/lib/api-client';
import { formatInr } from '@/lib/currency';

jest.mock('@/lib/api-client', () => ({
  getProduct: jest.fn(),
}));

const product = (id: string, name: string, memory: string) => ({
  id,
  name,
  brand: 'Example brand',
  description: null,
  category: 'Computers',
  sku: id,
  price: id === 'one' ? 50000 : 55000,
  list_price: null,
  image_url: null,
  image_alt: null,
  specifications: { Memory: memory, _internal: 'hidden' },
  stock_quantity: 2,
  max_purchase_quantity: 2,
});

describe('CompareExperience', () => {
  beforeEach(() => {
    sessionStorage.setItem('shopsmart-compare-ids', JSON.stringify(['one', 'two']));
    jest
      .mocked(getProduct)
      .mockImplementation(async (id) =>
        id === 'one' ? product('one', 'Model One', '16 GB') : product('two', 'Model Two', '32 GB')
      );
  });

  afterEach(() => {
    sessionStorage.clear();
    jest.resetAllMocks();
  });

  it('loads current catalog facts and offers a grounded assistant handoff', async () => {
    render(<CompareExperience />);

    expect(await screen.findByRole('link', { name: 'Ask AI about these' })).toHaveAttribute(
      'href',
      expect.stringContaining('Model%20One')
    );
    expect(screen.getByText(formatInr(50000))).toBeInTheDocument();
    expect(screen.queryByText('hidden')).not.toBeInTheDocument();
    expect(getProduct).toHaveBeenCalledTimes(2);
  });

  it('filters the matrix to authoritative values that differ', async () => {
    render(<CompareExperience />);
    await screen.findByText('Model One');

    fireEvent.click(screen.getByRole('checkbox', { name: 'Show differences only' }));

    await waitFor(() => expect(screen.queryByText('Availability')).not.toBeInTheDocument());
    expect(screen.getByText('Memory')).toBeInTheDocument();
    expect(screen.getByText('16 GB')).toBeInTheDocument();
    expect(screen.getByText('32 GB')).toBeInTheDocument();
  });

  it('keeps recovery available when a selected catalog product was removed', async () => {
    jest.mocked(getProduct).mockImplementation(async (id) => {
      if (id === 'one') throw new Error('Not found');
      return product('two', 'Model Two', '32 GB');
    });
    render(<CompareExperience />);

    expect(await screen.findByRole('alert')).toHaveTextContent('no longer available');
    fireEvent.click(screen.getByRole('button', { name: 'Remove product' }));
    await waitFor(() => expect(sessionStorage.getItem('shopsmart-compare-ids')).toBe('["two"]'));
  });

  it('refreshes when the shared compare tray changes its selected IDs', async () => {
    render(<CompareExperience />);
    await screen.findByText('Model One');
    sessionStorage.removeItem('shopsmart-compare-ids');
    act(() => window.dispatchEvent(new Event('shopsmart-compare')));

    expect(await screen.findByRole('link', { name: 'Browse catalog' })).toBeInTheDocument();
  });
});
