const categoryImages: Record<string, string> = {
  accessories: '/images/Home-Page-Cat-Images/Accessories_main_cat.png',
  beauty: '/images/Home-Page-Cat-Images/BeautyPersonalCare_main_cat.png',
  fashion: '/images/Home-Page-Cat-Images/Fashion_main_cat.png',
  footwear: '/images/Home-Page-Cat-Images/Footwear_main_cat.png',
  home: '/images/Home-Page-Cat-Images/HomeLiving_main_cat.png',
  appliances: '/images/Home-Page-Cat-Images/KitchenDining_main_cat.png',
  laptops: '/images/Home-Page-Cat-Images/Electronics_main_cat.png',
  phones: '/images/Home-Page-Cat-Images/Electronics_main_cat.png',
  groceries: '/images/Home-Page-Cat-Images/KitchenDining_main_cat.png',
};

export function categoryImageFor(category: string | null): string | undefined {
  return category ? categoryImages[category] : undefined;
}
