import Nav from '@/components/nav';
import { ProductDetails } from '@/components/ProductDetails';
import { cookies } from 'next/headers';

export default function ProductPage({ params }: { params: { productId: string } }) {
  const hasSessionCookie = cookies().has('session_id');

  return (
    <>
      <Nav probeAuth={hasSessionCookie} />
      <main id="main-content">
        <ProductDetails productId={params.productId} />
      </main>
    </>
  );
}
