import AuthenticatedLayout from '@/app/authenticated-layout';
import { OrderHistory } from '@/components/OrderHistory';

export default function OrdersPage() {
  return (
    <AuthenticatedLayout>
      <div className="mx-auto max-w-3xl space-y-8">
        <header className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-caps text-accent-700">Account</p>
          <h1 className="font-display text-display-md font-bold text-ink-900">Order history</h1>
        </header>
        <section className="rounded-tile border border-ink-100 bg-white p-5 shadow-tile sm:p-7">
          <OrderHistory />
        </section>
      </div>
    </AuthenticatedLayout>
  );
}
