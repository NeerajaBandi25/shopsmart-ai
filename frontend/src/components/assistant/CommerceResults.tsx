import Link from 'next/link';
import { formatInr } from '@/lib/currency';

export type ProductResult = {
  id: string;
  name: string;
  description: string | null;
  category?: string | null;
  sku: string;
  price_cents: number;
  stock_quantity: number;
  max_purchase_quantity?: number;
};

export type PromotionResult = {
  promotion_id: string;
  code: string | null;
  name: string;
  description: string | null;
  promotion_type: 'percentage' | 'fixed';
  value: number;
  scope_type: string;
  scope_category: string | null;
  min_cart_total_cents: number | null;
  max_discount_cents: number | null;
};

type CommerceResultsProps = {
  resultId: string;
  products?: ProductResult[];
  promotions?: PromotionResult[];
  addingProductId: string | null;
  cartAction: { resultId: string; kind: 'success' | 'error'; message: string } | null;
  onAddToCart: (productId: string, resultId: string) => void;
};

function ProductComparison({ products }: { products: ProductResult[] }) {
  if (products.length < 2) return null;

  return (
    <div className="mt-5">
      <h3 className="mb-2 text-sm font-semibold text-ink-900">Compare these results</h3>
      <div className="overflow-x-auto rounded border border-ink-200 bg-white">
        <table className="w-full min-w-[34rem] text-left text-sm">
          <caption className="sr-only">Catalog fields returned for these products</caption>
          <thead className="bg-gray-100 text-xs uppercase text-ink-600">
            <tr>
              <th scope="col" className="px-3 py-2 font-semibold">
                Product
              </th>
              <th scope="col" className="px-3 py-2 font-semibold">
                Category
              </th>
              <th scope="col" className="px-3 py-2 font-semibold">
                Price
              </th>
              <th scope="col" className="px-3 py-2 font-semibold">
                Availability
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {products.map((product) => (
              <tr key={product.id}>
                <th scope="row" className="px-3 py-3 font-medium text-ink-900">
                  {product.name}
                </th>
                <td className="px-3 py-3 text-ink-700">{product.category || 'Not provided'}</td>
                <td className="px-3 py-3 font-semibold text-ink-900">
                  {formatInr(product.price_cents)}
                </td>
                <td className="px-3 py-3 text-ink-700">
                  {product.stock_quantity > 0
                    ? `In stock (${product.stock_quantity})`
                    : 'Out of stock'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ProductResults({
  resultId,
  products,
  addingProductId,
  cartAction,
  onAddToCart,
}: Pick<
  CommerceResultsProps,
  'resultId' | 'products' | 'addingProductId' | 'cartAction' | 'onAddToCart'
>) {
  if (!products) return null;
  if (products.length === 0) {
    return (
      <p
        className="rounded border border-ink-200 bg-white px-4 py-3 text-sm text-ink-700"
        role="status"
      >
        No matching products were returned from the catalog.
      </p>
    );
  }

  return (
    <section aria-label="Product results">
      <p className="mb-3 text-sm text-ink-600">
        {products.length} {products.length === 1 ? 'catalog result' : 'catalog results'}
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {products.map((product) => (
          <article
            key={product.id}
            className="flex min-w-0 flex-col rounded border border-ink-200 bg-white p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-semibold text-ink-900">{product.name}</h3>
              <span className="shrink-0 font-semibold text-ink-900">
                {formatInr(product.price_cents)}
              </span>
            </div>
            {product.description && (
              <p className="mt-2 text-sm text-ink-600">{product.description}</p>
            )}
            <dl className="mt-3 space-y-1 text-xs text-ink-600">
              {product.category && (
                <div className="flex gap-1">
                  <dt>Category:</dt>
                  <dd>{product.category}</dd>
                </div>
              )}
              <div className="flex flex-wrap gap-x-1">
                <dt>SKU:</dt>
                <dd>{product.sku}</dd>
                <dt aria-hidden="true">·</dt>
                <dd>
                  {product.stock_quantity > 0
                    ? `${product.stock_quantity} in stock`
                    : 'Out of stock'}
                </dd>
              </div>
              {product.max_purchase_quantity !== undefined && (
                <div className="flex gap-1">
                  <dt>Purchase limit:</dt>
                  <dd>{product.max_purchase_quantity} per order</dd>
                </div>
              )}
            </dl>
            <div className="mt-auto flex flex-wrap gap-2 pt-4">
              <Link
                href={`/products/${encodeURIComponent(product.id)}`}
                className="inline-flex min-h-10 items-center rounded border border-ink-300 px-3 py-2 text-sm font-semibold text-ink-800 hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-600"
              >
                View product
              </Link>
              <button
                type="button"
                disabled={addingProductId !== null || product.stock_quantity < 1}
                onClick={() => onAddToCart(product.id, resultId)}
                className="min-h-10 rounded bg-accent-700 px-3 py-2 text-sm font-semibold text-white hover:bg-accent-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {addingProductId === product.id ? 'Adding…' : 'Add to cart'}
              </button>
            </div>
          </article>
        ))}
      </div>
      {cartAction?.resultId === resultId && (
        <p className="mt-3 text-sm" role={cartAction.kind === 'error' ? 'alert' : 'status'}>
          {cartAction.message}
        </p>
      )}
      <ProductComparison products={products} />
    </section>
  );
}

function PromotionResults({ promotions }: { promotions: PromotionResult[] }) {
  if (promotions.length === 0) {
    return (
      <p
        className="rounded border border-ink-200 bg-white px-4 py-3 text-sm text-ink-700"
        role="status"
      >
        No active offers were returned for this request.
      </p>
    );
  }

  return (
    <ul aria-label="Promotion results" className="divide-y divide-ink-100 border-y border-ink-200">
      {promotions.map((promotion) => (
        <li
          key={promotion.promotion_id}
          className="flex flex-col justify-between gap-2 py-4 sm:flex-row sm:gap-5"
        >
          <div className="min-w-0">
            <p className="font-semibold text-ink-900">{promotion.name}</p>
            {promotion.description && (
              <p className="mt-1 text-sm text-ink-600">{promotion.description}</p>
            )}
            {promotion.code && (
              <p className="mt-2 text-xs font-semibold uppercase text-accent-700">
                Code {promotion.code}
              </p>
            )}
            <p className="mt-2 text-xs text-ink-600">
              {promotion.scope_category
                ? `Category: ${promotion.scope_category}`
                : `Scope: ${promotion.scope_type}`}
              {promotion.min_cart_total_cents !== null &&
                ` · Minimum cart ${formatInr(promotion.min_cart_total_cents)}`}
              {promotion.max_discount_cents !== null &&
                ` · Maximum discount ${formatInr(promotion.max_discount_cents)}`}
            </p>
          </div>
          <p className="shrink-0 font-semibold text-leaf-700">
            {promotion.promotion_type === 'percentage'
              ? `${promotion.value}% off`
              : `${formatInr(promotion.value)} off`}
          </p>
        </li>
      ))}
    </ul>
  );
}

export default function CommerceResults({
  resultId,
  products,
  promotions,
  addingProductId,
  cartAction,
  onAddToCart,
}: CommerceResultsProps) {
  return (
    <div className="space-y-5">
      <ProductResults
        resultId={resultId}
        products={products}
        addingProductId={addingProductId}
        cartAction={cartAction}
        onAddToCart={onAddToCart}
      />
      {promotions && <PromotionResults promotions={promotions} />}
    </div>
  );
}
