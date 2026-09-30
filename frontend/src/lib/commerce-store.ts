import { create } from 'zustand';

interface CartCountSource {
  items: ReadonlyArray<{ quantity: number }>;
}

interface CommerceState {
  cartItemCount: number;
  syncCartCount: (cart: CartCountSource) => void;
  clearPrivateCommerce: () => void;
}

export const useCommerceStore = create<CommerceState>()((set) => ({
  cartItemCount: 0,
  syncCartCount: (cart) =>
    set({ cartItemCount: cart.items.reduce((count, item) => count + item.quantity, 0) }),
  clearPrivateCommerce: () => set({ cartItemCount: 0 }),
}));
