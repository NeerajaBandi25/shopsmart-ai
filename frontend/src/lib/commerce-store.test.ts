import { useCommerceStore } from './commerce-store';

describe('commerce store', () => {
  beforeEach(() => {
    useCommerceStore.getState().clearPrivateCommerce();
  });

  it('starts with an empty private commerce projection', () => {
    expect(useCommerceStore.getState().cartItemCount).toBe(0);
  });

  it('derives the item count from cart quantities', () => {
    useCommerceStore.getState().syncCartCount({
      items: [{ quantity: 2 }, { quantity: 3 }],
    });

    expect(useCommerceStore.getState().cartItemCount).toBe(5);
  });

  it('replaces the projection when the authoritative cart is empty', () => {
    useCommerceStore.getState().syncCartCount({ items: [{ quantity: 2 }] });
    useCommerceStore.getState().syncCartCount({ items: [] });

    expect(useCommerceStore.getState().cartItemCount).toBe(0);
  });

  it('clears private commerce state', () => {
    useCommerceStore.getState().syncCartCount({ items: [{ quantity: 4 }] });

    useCommerceStore.getState().clearPrivateCommerce();

    expect(useCommerceStore.getState().cartItemCount).toBe(0);
  });
});
