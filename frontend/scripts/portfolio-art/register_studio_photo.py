#!/usr/bin/env python3
"""Register one generated studio photograph against a portfolio image-family slot.

The generated original stays in Codex's image history; this utility copies it to
the public asset tree and refreshes the seed manifest's integrity metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = ROOT / "public" / "images" / "products" / "portfolio"
MANIFEST = ASSET_ROOT / "manifest.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--category", required=True)
    parser.add_argument("--index", type=int, choices=range(1, 6), required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--generator-receipt", required=True, help="Image-generation result identifier")
    args = parser.parse_args()
    if args.category not in {"laptops", "smartphones", "headphones", "smartwatches", "tablets", "cameras", "televisions", "gaming", "home_appliances", "kitchen_appliances", "fashion", "footwear", "beauty", "accessories", "home_living"}:
        parser.error(f"unsupported product category: {args.category}")
    if not args.source.is_file():
        parser.error(f"image source does not exist: {args.source}")

    source_payload = args.source.read_bytes()
    if source_payload[:8] != b"\x89PNG\r\n\x1a\n":
        parser.error("generated source is not a PNG image")
    width, height = struct.unpack(">II", source_payload[16:24])
    relative = Path(args.category) / f"{args.index:02d}.jpg"
    destination = ASSET_ROOT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    old_relative = relative.with_suffix(".png").as_posix()
    item = next(
        (image for image in manifest["images"] if image["file"] in {relative.as_posix(), old_relative}),
        None,
    )
    if item is None:
        parser.error(f"asset slot not present in manifest: {relative.as_posix()}")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(args.source), "-frames:v", "1", "-q:v", "3", str(destination)],
        check=True,
    )
    payload = destination.read_bytes()
    if payload[:2] != b"\xff\xd8":
        destination.unlink(missing_ok=True)
        parser.error("image optimizer did not produce a JPEG")
    item.update(
        {
            "file": relative.as_posix(),
            "subject": f"{args.category} product family {args.index:02d}",
            "width": width,
            "height": height,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "medium": "AI-generated photorealistic studio photograph, optimized JPEG",
            "generator": "OpenAI built-in image_gen",
            "generator_receipt": args.generator_receipt,
            "generation_brief": args.prompt,
            "external_assets": [],
            "branding": "Unbranded portfolio-family illustration; not a photograph of a specific SKU",
        }
    )
    manifest["provenance"] = (
        "ShopSmart portfolio-family images generated with the built-in OpenAI image_gen tool. "
        "Each record contains its generation prompt, receipt, dimensions, byte count and SHA-256. "
        "Images are unbranded illustrative portfolio-family photography, not a claim that the scene depicts a specific retail SKU."
    )
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ASSET_ROOT / args.category / f"{args.index:02d}.png").unlink(missing_ok=True)
    print(f"registered {relative.as_posix()} {width}x{height} {hashlib.sha256(payload).hexdigest()}")


if __name__ == "__main__":
    main()
