import Nav from '@/components/nav';

export default function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Nav />
      <main className="min-h-screen flex flex-col bg-gray-50">
        <div className="flex-1 py-8 px-4 sm:px-6 lg:px-8">{children}</div>
      </main>
    </>
  );
}
