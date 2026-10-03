import './../styles/globals.css';

export const metadata = {
  title: 'ShopSmart AI | Thoughtful product discovery',
  description: 'Explore product details, current prices, and useful shopping comparisons.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
