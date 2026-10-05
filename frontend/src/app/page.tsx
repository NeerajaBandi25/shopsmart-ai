import Nav from '@/components/nav';
import { cookies } from 'next/headers';
import { HomePageExperience } from '@/components/home/HomePageExperience';

export default async function HomePage() {
  const cookieStore = cookies();
  const hasSessionCookie = cookieStore.has('session_id');

  return (
    <>
      <Nav probeAuth={hasSessionCookie} />
      <HomePageExperience hasSession={hasSessionCookie} />
    </>
  );
}
