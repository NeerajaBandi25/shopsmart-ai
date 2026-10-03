#!/usr/bin/env python3
"""Verify all 75 public portfolio family images against the checked-in manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parents[2] / "public" / "images" / "products" / "portfolio"
EXPECTED = {
    f"{category}/{index:02d}.jpg"
    for category in (
        "laptops", "smartphones", "headphones", "smartwatches", "tablets",
        "cameras", "televisions", "gaming", "home_appliances",
        "kitchen_appliances", "fashion", "footwear", "beauty",
        "accessories", "home_living",
    )
    for index in range(1, 6)
}


def jpeg_dimensions(payload: bytes) -> tuple[int, int]:
    cursor = 2
    while cursor + 9 < len(payload):
        if payload[cursor] != 0xFF:
            cursor += 1
            continue
        marker = payload[cursor + 1]
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            cursor += 2
            continue
        length = int.from_bytes(payload[cursor + 2 : cursor + 4], "big")
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height = int.from_bytes(payload[cursor + 5 : cursor + 7], "big")
            width = int.from_bytes(payload[cursor + 7 : cursor + 9], "big")
            return width, height
        if length < 2:
            break
        cursor += 2 + length
    return 0, 0


def main() -> None:
    manifest = json.loads((ASSET_ROOT / "manifest.json").read_text(encoding="utf-8"))
    records = {record["file"]: record for record in manifest["images"]}
    missing, extra = EXPECTED - records.keys(), records.keys() - EXPECTED
    if missing or extra:
        raise SystemExit(f"manifest slot mismatch; missing={sorted(missing)}, extra={sorted(extra)}")

    total_bytes = 0
    for relative, record in records.items():
        path = ASSET_ROOT / relative
        payload = path.read_bytes()
        if payload[:2] != b"\xff\xd8":
            raise SystemExit(f"not a JPEG: {relative}")
        width, height = jpeg_dimensions(payload)
        if width < 1000 or height < 1000:
            raise SystemExit(f"unexpected source dimensions in manifest for {relative}: {width}x{height}")
        digest = hashlib.sha256(payload).hexdigest()
        if record.get("sha256") != digest or record.get("bytes") != len(payload):
            raise SystemExit(f"integrity metadata mismatch: {relative}")
        if not record.get("generator_receipt") or not record.get("generation_brief"):
            raise SystemExit(f"provenance missing: {relative}")
        total_bytes += len(payload)
    print(f"verified {len(records)} product-family photos, {total_bytes:,} bytes, hashes and provenance complete")


if __name__ == "__main__":
    main()
