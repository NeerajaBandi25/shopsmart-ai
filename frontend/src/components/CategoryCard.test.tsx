import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { CategoryCard } from './CategoryCard';

const props = {
  numeral: '01',
  name: 'Living Room',
  href: '/products?q=home',
  image: '/images/living-room.jpg',
  alt: 'A bright living room with a sofa and coffee table',
  badge: 'Curated Edit',
};

describe('CategoryCard', () => {
  it('renders the supplied image description, badge, and category name', () => {
    render(<CategoryCard {...props} />);

    expect(screen.getByRole('img', { name: props.alt })).toBeInTheDocument();
    expect(screen.getByText(props.badge)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: props.name, level: 3 })).toBeInTheDocument();
  });

  it('applies an explicitly supplied image focal position', () => {
    render(<CategoryCard {...props} objectPosition="35% 65%" />);

    expect(screen.getByRole('img', { name: props.alt })).toHaveStyle({
      objectPosition: '35% 65%',
    });
  });

  it('defaults the image focal position to 50% 50%', () => {
    render(<CategoryCard {...props} />);

    expect(screen.getByRole('img', { name: props.alt })).toHaveStyle({
      objectPosition: '50% 50%',
    });
  });

  it('renders as a navigable category link', () => {
    render(<CategoryCard {...props} />);

    expect(screen.getByRole('article')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Browse Living Room' })).toHaveAttribute(
      'href',
      props.href
    );
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
