import AuthenticatedLayout from '@/app/authenticated-layout';
import { CheckoutFlow } from '@/components/CheckoutFlow';

export default function CheckoutPage() {
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
        <CheckoutFlow />
      </div>
    </AuthenticatedLayout>
  );
}
