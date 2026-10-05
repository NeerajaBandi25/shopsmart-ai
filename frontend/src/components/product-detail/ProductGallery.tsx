'use client';

import { useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import type { Product } from '@/lib/api-client';

interface ProductGalleryProps {
  product: Product;
  categoryImage?: string;
}

export function ProductGallery({ product, categoryImage }: ProductGalleryProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [imageIndex, setImageIndex] = useState(0);
  const expandButton = useRef<HTMLButtonElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const gallery = product.image_gallery || [];
  const image = gallery[imageIndex]?.url || product.image_url || categoryImage;
  const isProductImage = Boolean(product.image_url);
  const imageAlt = isProductImage
    ? gallery[imageIndex]?.alt || product.image_alt || product.name
    : categoryImage
      ? `${product.category} category photograph; product-specific image unavailable`
      : 'Product image unavailable';

  useEffect(() => {
    if (!isExpanded) return;
    const returnFocusTo = expandButton.current;
    closeButton.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsExpanded(false);
      // The image dialog has one interactive control. Keep keyboard focus inside
      // it until dismissal, then restore the shopper's place in the gallery.
      if (event.key === 'Tab') {
        event.preventDefault();
        closeButton.current?.focus();
      }
    }
    window.addEventListener('keydown', closeOnEscape);
    return () => {
      window.removeEventListener('keydown', closeOnEscape);
      document.body.style.overflow = previousOverflow;
      returnFocusTo?.focus();
    };
  }, [isExpanded]);

  return (
    <figure>
      <div className="relative aspect-[4/3] overflow-hidden bg-sand-100">
        {image ? (
          <button
            ref={expandButton}
            type="button"
            onClick={() => setIsExpanded(true)}
            aria-label="Expand product image"
            className="absolute inset-0 block h-full w-full cursor-zoom-in focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-500"
          >
            <Image
              src={image}
              alt={imageAlt}
              fill
              priority
              sizes="(min-width: 1024px) 55vw, 100vw"
              className={isProductImage ? 'object-contain p-5' : 'object-cover'}
            />
          </button>
        ) : (
          <div
            role="img"
            aria-label="Product image unavailable"
            className="absolute inset-0 grid place-items-center bg-sand-100 p-4 text-center text-xs font-semibold uppercase tracking-caps text-ink-500"
          >
            Product image unavailable
          </div>
        )}
        {!isProductImage && categoryImage && (
          <span className="pointer-events-none absolute left-4 top-4 bg-white/90 px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-caps text-ink-700">
            Category image
          </span>
        )}
      </div>
      {!!gallery.length && (
        <div className="mt-3 flex gap-2" aria-label="Product image thumbnails">
          {gallery.map((item, index) => (
            <button
              key={item.url}
              type="button"
              aria-label={`Show product image ${index + 1}`}
              aria-pressed={index === imageIndex}
              onClick={() => setImageIndex(index)}
              className={`relative h-16 w-16 overflow-hidden rounded-lg border-2 ${index === imageIndex ? 'border-accent-600' : 'border-ink-200'}`}
            >
              <Image src={item.url} alt={item.alt} fill sizes="64px" className="object-contain" />
            </button>
          ))}
        </div>
      )}
      {isProductImage && product.image_creator && product.image_license && (
        <figcaption className="mt-3 text-xs leading-relaxed text-ink-500">
          Image by{' '}
          {product.image_source_url ? (
            <a
              href={product.image_source_url}
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2"
            >
              {product.image_creator}
            </a>
          ) : (
            product.image_creator
          )}{' '}
          ·{' '}
          {product.image_license_url ? (
            <a
              href={product.image_license_url}
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2"
            >
              {product.image_license}
            </a>
          ) : (
            product.image_license
          )}
        </figcaption>
      )}
      {!isProductImage && categoryImage && (
        <figcaption className="mt-3 text-xs leading-relaxed text-ink-500">
          Category photography is shown because a product-specific image has not been supplied.
        </figcaption>
      )}
      {isExpanded && image && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`${product.name} image`}
          className="fixed inset-0 z-50 grid place-items-center bg-ink-950/90 p-4 sm:p-10"
          onClick={(event) => {
            if (event.target === event.currentTarget) setIsExpanded(false);
          }}
        >
          <button
            ref={closeButton}
            type="button"
            onClick={() => setIsExpanded(false)}
            className="absolute right-4 top-4 h-10 border border-white/50 px-3 text-sm font-semibold text-white hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
          >
            Close image
          </button>
          <div className="relative h-full max-h-[85vh] w-full max-w-6xl">
            <Image src={image} alt={imageAlt} fill sizes="100vw" className="object-contain" />
          </div>
        </div>
      )}
    </figure>
  );
}
