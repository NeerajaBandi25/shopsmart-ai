import Nav from '@/components/nav';
import { ProductCatalog } from '@/components/ProductCatalog';
import { cookies } from 'next/headers';

interface ProductsPageProps {
  searchParams: Record<string, string | string[] | undefined>;
}

function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default function ProductsPage({ searchParams }: ProductsPageProps) {
  const hasSessionCookie = cookies().has('session_id');
  const category = firstParam(searchParams.category);
  const search = firstParam(searchParams.q);

  return (
    <>
      <Nav probeAuth={hasSessionCookie} />
      <main>
        <ProductCatalog initialCategory={category} initialSearch={search} />
      </main>
    </>
  );
}