import Nav from '@/components/nav';
import { ProductCatalog } from '@/components/ProductCatalog';
import { cookies } from 'next/headers';
import { readCatalogQuery } from '@/lib/catalog-query';

interface ProductsPageProps {
  searchParams: Record<string, string | string[] | undefined>;
}

function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default function ProductsPage({ searchParams }: ProductsPageProps) {
  const hasSessionCookie = cookies().has('session_id');
  const filters = readCatalogQuery(searchParams);
  const skipValue = Number(firstParam(searchParams.skip));
  const skip = Number.isSafeInteger(skipValue) && skipValue > 0 ? skipValue : 0;

  return (
    <>
      <Nav probeAuth={hasSessionCookie} />
      <main>
        <ProductCatalog
          key={JSON.stringify(searchParams)}
          initialFilters={filters}
          initialSkip={skip}
        />
      </main>
    </>
  );
}
