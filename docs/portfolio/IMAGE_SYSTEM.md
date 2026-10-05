# ShopSmart portfolio image system

The portfolio catalog has 75 unbranded, photo-style family images: five images for each of its 15 seeded departments. The 1254-pixel square masters are published as optimized JPEGs. They were generated for this repository with the built-in image-generation tool; the manifest records the family slot, generation brief and receipt, dimensions, byte size, and SHA-256 digest. No retailer photos, product logos, or external image URLs are used.

These are illustrative portfolio-family images, not evidence that a photo depicts the exact model or package of a fictional seeded listing. The catalog keeps its published specifications and variant data authoritative. Its backend returns the image URL and alt text with the product, and builds image_gallery from the same stored presentation metadata. The gallery shows only supplied images; the frontend does not invent extra angles.

Run python frontend/scripts/portfolio-art/validate_studio_manifest.py to verify that all 75 JPEGs exist, retain their expected dimensions, and match their SHA-256 and byte-count records. Register a new image-family photo with register_studio_photo.py; that command optimizes the generated PNG with ffmpeg, updates the image manifest, and removes the replaced illustration only after a valid JPEG has been written.
