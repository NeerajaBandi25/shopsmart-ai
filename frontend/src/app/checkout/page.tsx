import AuthenticatedLayout from '@/app/authenticated-layout';
import { CheckoutForm, type CheckoutLine } from '@/components/CheckoutForm';

type SearchValue = string | string[] | undefined;

function asList(value: SearchValue): string[] {
  if (Array.isArray(value)) return value;
  return value ? [value] : [];
}

export default function CheckoutPage({
  searchParams,
}: {
  searchParams: { product_id?: SearchValue; quantity?: SearchValue };
}) {
  const productIds = asList(searchParams.product_id);
  const quantities = asList(searchParams.quantity);
  const items: CheckoutLine[] = productIds.flatMap((product_id, index) => {
    const quantity = Number(quantities[index]);
    return product_id && Number.isSafeInteger(quantity) && quantity > 0
      ? [{ product_id, quantity }]
      : [];
  });

  return (
    <AuthenticatedLayout>
      <div className="mx-auto max-w-3xl space-y-8">
        <header className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-caps text-accent-700">Checkout</p>
          <h1 className="font-display text-display-md font-bold text-ink-900">Review your order</h1>
          <p className="text-sm text-ink-500">
            Final prices and availability are confirmed when you place the order.
          </p>
        </header>
        <section className="rounded-tile border border-ink-100 bg-white p-5 shadow-tile sm:p-7">
          <CheckoutForm items={items} />
        </section>
      </div>
    </AuthenticatedLayout>
  );
}
