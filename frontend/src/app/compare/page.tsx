import Nav from '@/components/nav';
import { CompareExperience } from '@/components/CompareExperience';

export default function ComparePage() {
  return (
    <>
      <Nav />
      <main className="min-h-screen bg-[#f7f5f1] px-4 py-10 text-ink-900 sm:px-8 lg:px-12">
        <CompareExperience />
      </main>
    </>
  );
}
