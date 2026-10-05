import './../styles/globals.css';
import { ShoppingTools } from '@/components/ShoppingTools';

export const metadata = {
  title: 'ShopSmart AI | Thoughtful product discovery',
  description: 'Explore product details, current prices, and useful shopping comparisons.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ShoppingTools />
        {children}
      </body>
    </html>
  );
}
