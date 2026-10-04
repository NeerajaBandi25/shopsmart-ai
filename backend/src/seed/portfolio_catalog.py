"""Add a deterministic fictional catalog to the dedicated local portfolio database."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import or_, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.product import Product
from src.seed.portfolio_profiles import aligned_families, product_configuration

CATALOG_VERSION = "portfolio-catalog-v2"
CATALOG_DATABASE = "shopsmart_portfolio"
CATALOG_OPT_IN = "SHOPSMART_ALLOW_CATALOG_FIXTURE_SEED"
LOCAL_ENVIRONMENTS = {"local", "dev", "development", "test"}
PRODUCTION_ENVIRONMENTS = {"prod", "production", "stage", "staging"}

_SOURCE_CATALOG_FAMILIES: dict[str, dict[str, Any]] = {
    "laptops": {
        "brands": ("Vellune", "Orbiant", "Caldrin", "Merroway"),
        "variants": (
            ("8 GB RAM / 256 GB SSD", "Graphite", 0),
            ("8 GB RAM / 256 GB SSD", "Silver", 0),
            ("16 GB RAM / 512 GB SSD", "Graphite", 650000),
            ("16 GB RAM / 512 GB SSD", "Silver", 650000),
            ("16 GB RAM / 1 TB SSD", "Graphite", 1450000),
            ("16 GB RAM / 1 TB SSD", "Silver", 1450000),
            ("32 GB RAM / 1 TB SSD", "Graphite", 2950000),
            ("32 GB RAM / 1 TB SSD", "Silver", 2950000),
        ),
        "products": (
            (
                "student notebooks",
                "14-inch Study Laptop",
                4899000,
                "14-inch anti-glare IPS display",
            ),
            (
                "business notebooks",
                "Quiet Office Laptop",
                7299000,
                "1080p webcam and privacy shutter",
            ),
            (
                "creator notebooks",
                "Colorwork Laptop",
                9499000,
                "100% sRGB color-calibrated display",
            ),
            (
                "convertible laptops",
                "Foldline 2-in-1 Laptop",
                8499000,
                "360-degree hinge with touch display",
            ),
            (
                "travel notebooks",
                "Featherweight Laptop",
                6799000,
                "Magnesium chassis weighing 1.2 kg",
            ),
            (
                "gaming notebooks",
                "Thermal Ridge Gaming Laptop",
                11999000,
                "Dual-fan cooling and 165 Hz display",
            ),
            (
                "workstation laptops",
                "Draftwell Mobile Workstation",
                14999000,
                "Dedicated graphics for 3D workloads",
            ),
            (
                "large-screen notebooks",
                "Panorama 16 Laptop",
                8999000,
                "16-inch 16:10 display with numeric keypad",
            ),
            (
                "rugged notebooks",
                "Fieldmark Durable Laptop",
                7999000,
                "Spill-resistant keyboard and reinforced corners",
            ),
            (
                "fanless notebooks",
                "Stillwater Silent Laptop",
                6199000,
                "Fanless design for quiet shared spaces",
            ),
        ),
    },
    "phones": {
        "brands": ("Avenell", "Nivora", "Ostel", "Ternwick"),
        "variants": (
            ("128 GB storage / 8 GB RAM", "Midnight", 0),
            ("128 GB storage / 8 GB RAM", "Glacier", 0),
            ("256 GB storage / 8 GB RAM", "Midnight", 350000),
            ("256 GB storage / 8 GB RAM", "Glacier", 350000),
            ("256 GB storage / 12 GB RAM", "Moss", 650000),
            ("256 GB storage / 12 GB RAM", "Rosewood", 650000),
            ("512 GB storage / 12 GB RAM", "Moss", 1250000),
            ("512 GB storage / 12 GB RAM", "Rosewood", 1250000),
        ),
        "products": (
            (
                "compact smartphones",
                "Pocketline 5G Phone",
                1799000,
                "6.1-inch OLED panel with optical stabilization",
            ),
            (
                "camera smartphones",
                "Clearframe Camera Phone",
                4299000,
                "50 MP main camera with a 2x portrait lens",
            ),
            ("large-screen smartphones", "Wideview 5G Phone", 2999000, "6.7-inch 120 Hz display"),
            (
                "long-life smartphones",
                "Daymark Battery Phone",
                2199000,
                "5,200 mAh battery with 30 W charging",
            ),
            (
                "foldable smartphones",
                "Hingeleaf Fold Phone",
                8999000,
                "Foldable inner display with reinforced hinge",
            ),
            (
                "rugged smartphones",
                "Trailguard Phone",
                2699000,
                "IP68 water resistance and textured grip",
            ),
            ("entry smartphones", "Meadow 5G Phone", 1299000, "90 Hz LCD with dual-SIM support"),
            (
                "secure smartphones",
                "Lockwood Privacy Phone",
                3599000,
                "Hardware privacy switch and five-year updates",
            ),
            (
                "gaming smartphones",
                "Arcade Current Phone",
                3899000,
                "240 Hz touch sampling and vapor chamber",
            ),
            (
                "accessibility smartphones",
                "Clearcall Easy Phone",
                1599000,
                "High-contrast interface and configurable side key",
            ),
        ),
    },
    "accessories": {
        "brands": ("Brackenel", "Lumaire Works", "Verdan Supply", "Solvane Goods"),
        "variants": (
            ("Compact", "Charcoal", 0),
            ("Compact", "Sage", 0),
            ("Standard", "Charcoal", 8000),
            ("Standard", "Sage", 8000),
            ("Large", "Ink", 18000),
            ("Large", "Clay", 18000),
            ("Travel set", "Ink", 32000),
            ("Travel set", "Clay", 32000),
        ),
        "products": (
            (
                "charging",
                "Braided USB-C Cable",
                12900,
                "100 W power delivery with reinforced connectors",
            ),
            (
                "charging",
                "Fold-flat Dual Charger",
                69900,
                "Two USB-C ports with a 45 W combined output",
            ),
            ("carrying", "Padded Device Sleeve", 89900, "Recycled canvas shell with a felt lining"),
            (
                "travel",
                "Modular Cable Organizer",
                45900,
                "Three removable pockets for travel essentials",
            ),
            ("audio", "Over-ear Headphone Case", 54900, "Molded interior with a mesh cable pocket"),
            (
                "desk",
                "Adjustable Laptop Stand",
                119900,
                "Six viewing angles with silicone contact pads",
            ),
            ("mobile", "Magnetic Desk Mount", 79900, "Weighted base with a 360-degree swivel"),
            (
                "input",
                "Compact Wireless Keyboard",
                189900,
                "Low-profile keys with multi-device pairing",
            ),
            ("power", "Pocket Power Bank", 99900, "10,000 mAh capacity with pass-through charging"),
            (
                "protection",
                "Tempered Glass Screen Kit",
                29900,
                "Two edge-to-edge protectors and alignment tray",
            ),
        ),
    },
    "footwear": {
        "brands": ("Merevale", "Ashmere", "Rillford", "Pinecross"),
        "variants": (
            ("UK 6", "Stone", 0),
            ("UK 7", "Stone", 0),
            ("UK 8", "Stone", 0),
            ("UK 9", "Stone", 0),
            ("UK 6", "Deep Navy", 0),
            ("UK 7", "Deep Navy", 0),
            ("UK 8", "Deep Navy", 0),
            ("UK 9", "Deep Navy", 0),
        ),
        "products": (
            (
                "road running",
                "Stridewell Road Runner",
                429900,
                "Breathable mesh upper with a 28 mm cushioned heel",
            ),
            ("walking", "Harbor Walk Sneaker", 319900, "Flexible rubber outsole and padded collar"),
            (
                "trail running",
                "Fernpath Trail Shoe",
                519900,
                "Lugged outsole and toe bumper for loose paths",
            ),
            (
                "everyday flats",
                "Lowbank Leather Flat",
                289900,
                "Soft leather lining with a cushioned footbed",
            ),
            (
                "hiking",
                "Ridgeline Mid Boot",
                689900,
                "Water-resistant upper and supportive ankle collar",
            ),
            (
                "court sports",
                "Baseline Court Shoe",
                379900,
                "Stable sidewall and non-marking rubber sole",
            ),
            (
                "sandals",
                "Tidepool Walking Sandal",
                229900,
                "Adjustable straps with a contoured footbed",
            ),
            (
                "formal",
                "Stillwell Derby Shoe",
                549900,
                "Polished leather upper with a stitched welt",
            ),
            (
                "slippers",
                "Cloudrest House Slipper",
                149900,
                "Washable knit upper with a non-slip sole",
            ),
            (
                "cycling",
                "Northbank Cycling Shoe",
                599900,
                "Ventilated upper with a stiff composite plate",
            ),
        ),
    },
    "fashion": {
        "brands": ("Willowmere", "Cedarline Studio", "Fallow & Thread", "Sablewick"),
        "variants": (
            ("S", "Ecru", 0),
            ("M", "Ecru", 0),
            ("L", "Ecru", 0),
            ("XL", "Ecru", 0),
            ("S", "Ink", 0),
            ("M", "Ink", 0),
            ("L", "Ink", 0),
            ("XL", "Ink", 0),
        ),
        "products": (
            ("shirts", "Everyday Oxford Shirt", 249900, "Cotton poplin with a button-down collar"),
            (
                "knitwear",
                "Ribbed Merino Crewneck",
                389900,
                "Fine-gauge merino blend with set-in sleeves",
            ),
            (
                "outerwear",
                "Canvas Field Jacket",
                599900,
                "Midweight cotton canvas with four patch pockets",
            ),
            (
                "trousers",
                "Straight-leg Twill Trouser",
                319900,
                "Stretch cotton twill with a clean front",
            ),
            ("dresses", "Linen Day Dress", 429900, "Breathable linen blend with side pockets"),
            ("skirts", "Pleated Midi Skirt", 299900, "Soft drape fabric with a concealed side zip"),
            (
                "activewear",
                "Studio Training Legging",
                279900,
                "Squat-tested stretch knit with a high waist",
            ),
            (
                "sleepwear",
                "Brushed Cotton Sleep Set",
                349900,
                "Two-piece set with a relaxed button top",
            ),
            (
                "basics",
                "Heavyweight Pocket Tee",
                119900,
                "Combed cotton jersey with a bound neckline",
            ),
            (
                "workwear",
                "Relaxed Cotton Overshirt",
                329900,
                "Garment-washed cotton with two chest pockets",
            ),
        ),
    },
    "appliances": {
        "brands": ("Morrowen", "Elderglen", "Ruskvale", "Alderwick"),
        "variants": (
            ("Standard", "Matte White", 0),
            ("Standard", "Graphite", 0),
            ("Plus", "Matte White", 35000),
            ("Plus", "Graphite", 35000),
            ("Family", "Matte White", 95000),
            ("Family", "Graphite", 95000),
            ("Quiet edition", "Matte White", 125000),
            ("Quiet edition", "Graphite", 125000),
        ),
        "products": (
            (
                "food preparation",
                "Two-speed Glass Blender",
                349900,
                "1.5 L jug with pulse control and removable blades",
            ),
            (
                "food preparation",
                "Compact Food Processor",
                499900,
                "Seven-cup bowl with slicing and grating discs",
            ),
            (
                "breakfast",
                "Two-slice Morning Toaster",
                269900,
                "Six browning settings and removable crumb tray",
            ),
            (
                "beverages",
                "Temperature-select Kettle",
                319900,
                "1.7 L capacity with five temperature presets",
            ),
            ("coffee", "Burr Coffee Grinder", 429900, "Conical steel burrs with 18 grind settings"),
            (
                "cleaning",
                "Cyclone Stick Vacuum",
                799900,
                "Washable filter and 40-minute cordless runtime",
            ),
            ("climate", "Ceramic Room Heater", 389900, "Two heat levels with tip-over protection"),
            (
                "laundry",
                "Fabric Care Steam Iron",
                229900,
                "Continuous steam with an anti-drip soleplate",
            ),
            (
                "air quality",
                "HEPA Room Air Cleaner",
                899900,
                "Three-stage filtration for rooms up to 30 square metres",
            ),
            (
                "personal care",
                "Foldable Ionic Hair Dryer",
                249900,
                "Two heat settings with a cool-shot button",
            ),
        ),
    },
    "home": {
        "brands": ("Tern & Timber", "Mossbank Home", "Elowen House", "Hearthvale"),
        "variants": (
            ("Single", "Natural", 0),
            ("Single", "Indigo", 0),
            ("Double", "Natural", 25000),
            ("Double", "Indigo", 25000),
            ("Set of 2", "Natural", 42000),
            ("Set of 2", "Indigo", 42000),
            ("Set of 4", "Natural", 79000),
            ("Set of 4", "Indigo", 79000),
        ),
        "products": (
            ("bedding", "Washed Cotton Duvet Cover", 289900, "Stonewashed cotton with corner ties"),
            (
                "bath",
                "Waffle-weave Bath Towel",
                69900,
                "Absorbent cotton terry with a hanging loop",
            ),
            ("lighting", "Ceramic Table Lamp", 219900, "Linen shade with a fabric-covered cord"),
            (
                "decor",
                "Hand-thrown Stoneware Vase",
                119900,
                "Glazed stoneware with a watertight interior",
            ),
            (
                "tableware",
                "Everyday Porcelain Dinner Plate",
                39900,
                "Dishwasher-safe porcelain with a raised rim",
            ),
            (
                "storage",
                "Lidded Woven Storage Basket",
                149900,
                "Woven paper cord over a sturdy metal frame",
            ),
            (
                "textiles",
                "Cotton Herringbone Throw",
                189900,
                "Midweight woven cotton with a brushed finish",
            ),
            (
                "curtains",
                "Linen-blend Curtain Panel",
                179900,
                "Light-filtering weave with a rod pocket",
            ),
            ("rugs", "Flatweave Entry Mat", 99900, "Reversible cotton weave with a low profile"),
            (
                "organization",
                "Modular Drawer Organizer",
                59900,
                "Four washable bins for adjustable storage",
            ),
        ),
    },
    "beauty": {
        "brands": ("Serein Formulary", "Fernhollow", "Cloverell", "Dewmere"),
        "variants": (
            ("30 ml", "Unscented", 0),
            ("50 ml", "Unscented", 18000),
            ("75 ml", "Unscented", 32000),
            ("100 ml", "Unscented", 49000),
            ("30 ml", "Citrus leaf", 5000),
            ("50 ml", "Citrus leaf", 23000),
            ("75 ml", "Citrus leaf", 37000),
            ("100 ml", "Citrus leaf", 54000),
        ),
        "products": (
            (
                "facial care",
                "Barrier Support Moisturizer",
                89900,
                "Ceramides and glycerin in a fragrance-free cream",
            ),
            ("cleansing", "Gentle Oat Cleanser", 64900, "Low-foam cleanser with colloidal oat"),
            (
                "sun care",
                "Daily Mineral Sunscreen SPF 40",
                99900,
                "Zinc oxide formula with a sheer, non-tinted finish",
            ),
            (
                "hair care",
                "Nourishing Scalp Shampoo",
                79900,
                "Sulfate-free wash with panthenol and oat extract",
            ),
            (
                "body care",
                "Shea Hand Balm",
                49900,
                "Rich hand cream with shea butter and no added fragrance",
            ),
            (
                "lip care",
                "Tinted Botanical Lip Balm",
                39900,
                "Plant-oil balm with a soft berry tint",
            ),
            (
                "serums",
                "Niacinamide Face Serum",
                109900,
                "Lightweight 5% niacinamide serum for daily use",
            ),
            ("bath", "Mineral Soak Blend", 59900, "Magnesium salt bath blend with dried lavender"),
            (
                "shaving",
                "Sensitive Skin Shave Cream",
                54900,
                "Cushioning shave cream with aloe leaf juice",
            ),
            (
                "oral care",
                "Soft-bristle Toothbrush Pair",
                29900,
                "Two recyclable-handle brushes with tapered bristles",
            ),
        ),
    },
    "groceries": {
        "brands": ("Fieldnote Pantry", "Juniper Mill", "Rill & Grain", "Mallowbrook Foods"),
        "variants": (
            ("250 g", None, 0),
            ("500 g", None, 14000),
            ("750 g", None, 26000),
            ("1 kg", None, 39000),
            ("2-pack, 250 g each", None, 16000),
            ("2-pack, 500 g each", None, 42000),
            ("Family pack, 1.5 kg", None, 69000),
            ("Pantry pack, 2 kg", None, 99000),
        ),
        "products": (
            ("grains", "Stone-ground Rolled Oats", 24900, "Whole-grain oats with no added sugar"),
            ("pulses", "Red Lentils", 19900, "Unpolished red lentils, sorted and ready to cook"),
            ("tea", "Assam Breakfast Tea", 28900, "Bold black tea from small Assam gardens"),
            (
                "coffee",
                "Medium-roast Ground Coffee",
                39900,
                "Chocolate notes from a washed Arabica blend",
            ),
            (
                "baking",
                "Unbleached Bread Flour",
                17900,
                "Stone-milled wheat flour for breads and pizza",
            ),
            (
                "spices",
                "Single-origin Turmeric",
                14900,
                "Bright ground turmeric with a warm, earthy aroma",
            ),
            (
                "snacks",
                "Sea-salted Millet Crisps",
                22900,
                "Oven-baked millet snack with a light salt finish",
            ),
            ("breakfast", "Almond Butter", 49900, "Roasted almonds ground without palm oil"),
            (
                "pantry",
                "Cold-pressed Sesame Oil",
                36900,
                "Unrefined sesame oil for dressings and finishing",
            ),
            (
                "dried fruit",
                "Unsweetened Dried Apricots",
                32900,
                "Sun-dried fruit with no added preservatives",
            ),
        ),
    },
    "furniture": {
        "brands": ("Oak & Estuary", "Brindlewood", "Lindenstead", "Morrowfield"),
        "variants": (
            ("Compact", "Natural oak", 0),
            ("Compact", "Walnut", 0),
            ("Standard", "Natural oak", 85000),
            ("Standard", "Walnut", 85000),
            ("Wide", "Natural oak", 175000),
            ("Wide", "Walnut", 175000),
            ("Storage edition", "Natural oak", 245000),
            ("Storage edition", "Walnut", 245000),
        ),
        "products": (
            (
                "desks",
                "Two-drawer Writing Desk",
                1299900,
                "Solid beech legs with a cable pass-through",
            ),
            ("seating", "Curved-back Dining Chair", 649900, "Steam-bent frame with a woven seat"),
            (
                "shelving",
                "Open-frame Bookcase",
                899900,
                "Five adjustable shelves with wall-fixings included",
            ),
            ("tables", "Round Pedestal Side Table", 379900, "Stable turned base with a 45 cm top"),
            (
                "bedroom",
                "Low-profile Bedside Cabinet",
                529900,
                "Soft-close drawer and a lower open shelf",
            ),
            (
                "storage",
                "Three-door Entry Cabinet",
                999900,
                "Adjustable interior shelf with soft-close hinges",
            ),
            (
                "work chairs",
                "Ergonomic Task Chair",
                1149900,
                "Adjustable lumbar support and breathable mesh back",
            ),
            (
                "dining",
                "Extendable Farmhouse Table",
                1899900,
                "Seats six and extends with a leaf insert",
            ),
            (
                "lounging",
                "Compact Reading Chair",
                1399900,
                "Supportive foam cushion with removable cover",
            ),
            (
                "outdoor",
                "Slatted Balcony Bench",
                729900,
                "Weather-treated acacia with a 180 kg capacity",
            ),
        ),
    },
    "sports": {
        "brands": ("Pacewell", "Arborstride", "Meridian Field", "Wilderun"),
        "variants": (
            ("Beginner", "Charcoal", 0),
            ("Beginner", "Moss", 0),
            ("Intermediate", "Charcoal", 35000),
            ("Intermediate", "Moss", 35000),
            ("Advanced", "Charcoal", 85000),
            ("Advanced", "Moss", 85000),
            ("Club set", "Charcoal", 125000),
            ("Club set", "Moss", 125000),
        ),
        "products": (
            (
                "yoga",
                "Cork-grip Yoga Mat",
                189900,
                "4 mm natural cork surface over non-slip rubber",
            ),
            ("strength", "Adjustable Kettlebell", 499900, "Weight plates adjust from 4 to 12 kg"),
            (
                "cycling",
                "All-weather Cycling Helmet",
                329900,
                "Impact-absorbing liner with 12 ventilation channels",
            ),
            (
                "racket sports",
                "Control-balance Tennis Racket",
                419900,
                "Graphite frame with a 100-square-inch head",
            ),
            (
                "swimming",
                "Open-water Swim Goggles",
                149900,
                "Anti-fog lenses with a wide peripheral view",
            ),
            (
                "camping",
                "Two-person Trail Tent",
                899900,
                "Freestanding design with a 2,000 mm rainfly",
            ),
            (
                "team sports",
                "Hand-stitched Training Football",
                199900,
                "Textured synthetic cover for grass and turf",
            ),
            (
                "fitness",
                "Heart-rate Training Watch",
                1299900,
                "GPS tracking with seven-day typical battery life",
            ),
            (
                "hiking",
                "Trekking Pole Pair",
                279900,
                "Three-section aluminum shafts with cork grips",
            ),
            (
                "recovery",
                "Textured Mobility Roller",
                89900,
                "EPP foam roller with a medium-firm surface",
            ),
        ),
    },
    "toys": {
        "brands": ("Pebblepath Play", "Foxglove Workshop", "Little Vellum", "Brightfern"),
        "variants": (
            ("Starter set", "Primary", 0),
            ("Starter set", "Woodland", 0),
            ("Expanded set", "Primary", 28000),
            ("Expanded set", "Woodland", 28000),
            ("Gift set", "Primary", 55000),
            ("Gift set", "Woodland", 55000),
            ("Classroom set", "Primary", 95000),
            ("Classroom set", "Woodland", 95000),
        ),
        "products": (
            (
                "building",
                "Maple Block Builder",
                149900,
                "48 smooth-edged blocks in five geometric shapes",
            ),
            (
                "puzzles",
                "Coastal Habitat Jigsaw",
                79900,
                "500-piece puzzle printed with vegetable inks",
            ),
            (
                "pretend play",
                "Market Stall Play Set",
                229900,
                "Wooden counter with felt produce and paper tokens",
            ),
            (
                "science",
                "Backyard Weather Lab",
                189900,
                "Child-safe tools for measuring rainfall and wind",
            ),
            (
                "crafts",
                "Watercolor Discovery Kit",
                69900,
                "Washable paints, thick paper, and a mixing tray",
            ),
            (
                "plush",
                "Sleepy Otter Plush",
                59900,
                "Recycled-fiber filling and embroidered features",
            ),
            (
                "board games",
                "Lantern Grove Cooperative Game",
                129900,
                "A cooperative woodland game for two to four players",
            ),
            (
                "music",
                "Four-note Wooden Xylophone",
                89900,
                "Tuned metal bars with two soft mallets",
            ),
            ("outdoor play", "Foldaway Garden Kite", 49900, "Ripstop sail with a 30 m flying line"),
            (
                "early learning",
                "Shape and Color Sorting Tray",
                99900,
                "Ten beech shapes with a washable cotton storage bag",
            ),
        ),
    },
    "books": {
        "brands": ("Paperbark Press", "Low Lantern Books", "Alder Quill", "Westmere Editions"),
        "variants": (
            ("Paperback", None, 0),
            ("Hardcover", None, 22000),
            ("Large-print paperback", None, 18000),
            ("Illustrated hardcover", None, 39000),
            ("Paperback gift edition", None, 27000),
            ("Clothbound edition", None, 52000),
            ("Library binding", None, 45000),
            ("Audio companion edition", None, 33000),
        ),
        "products": (
            (
                "literary fiction",
                "The Quiet Mapmaker",
                49900,
                "A coastal cartographer returns to redraw her childhood town",
            ),
            (
                "mystery",
                "The Orchard Ledger",
                52900,
                "A village archivist follows a missing account book",
            ),
            (
                "historical fiction",
                "Letters from the Glasshouse",
                57900,
                "Two generations of gardeners share a city conservatory",
            ),
            (
                "science",
                "Small Worlds, Deep Time",
                64900,
                "An illustrated introduction to geology and Earth's history",
            ),
            (
                "nature",
                "Birdsong Along the Estuary",
                59900,
                "Field notes and seasonal sketches from a tidal landscape",
            ),
            (
                "cooking",
                "A Table for the Rainy Season",
                69900,
                "Vegetable-forward recipes organized by pantry staples",
            ),
            (
                "personal finance",
                "The Patient Ledger",
                54900,
                "A practical guide to household budgeting and long-term saving",
            ),
            (
                "craft",
                "Mending Cloth by Hand",
                49900,
                "Visible-mending techniques with step-by-step diagrams",
            ),
            (
                "children's fiction",
                "Mina and the Paper Moon",
                39900,
                "A gentle illustrated story about a night-time paper boat",
            ),
            (
                "travel",
                "Walking the Old Canal",
                62900,
                "A route guide to towpaths, lock towns, and waterside wildlife",
            ),
        ),
    },
    "automotive": {
        "brands": ("Roadstead", "Copperline Garage", "Milefern", "Northspan Auto"),
        "variants": (
            ("Universal fit", "Black", 0),
            ("Universal fit", "Slate", 0),
            ("Compact fit", "Black", 12000),
            ("Compact fit", "Slate", 12000),
            ("Pair", "Black", 25000),
            ("Pair", "Slate", 25000),
            ("Workshop set", "Black", 49000),
            ("Workshop set", "Slate", 49000),
        ),
        "products": (
            (
                "interior care",
                "Microfiber Detailing Cloth Set",
                59900,
                "Six lint-free cloths for glass and painted surfaces",
            ),
            (
                "cargo",
                "Collapsible Trunk Organizer",
                89900,
                "Three compartments with non-slip base panels",
            ),
            (
                "charging",
                "12 V Dual-port Car Charger",
                49900,
                "USB-C power delivery with a protected 12 V plug",
            ),
            (
                "safety",
                "Compact First-aid Vehicle Kit",
                79900,
                "Weather-resistant case with road-trip essentials",
            ),
            (
                "maintenance",
                "Digital Tire-pressure Gauge",
                69900,
                "Backlit display with four selectable pressure units",
            ),
            (
                "cleaning",
                "Long-reach Wheel Brush",
                44900,
                "Soft split-tip bristles for wheel faces and barrels",
            ),
            (
                "visibility",
                "Rechargeable Inspection Light",
                129900,
                "Magnetic base with a 500-lumen work beam",
            ),
            (
                "comfort",
                "Breathable Seat Support Cushion",
                119900,
                "Washable mesh cover with contoured foam",
            ),
            (
                "organization",
                "Seatback Storage Panel",
                74900,
                "Five pockets sized for maps, bottles, and cables",
            ),
            (
                "emergency",
                "Reflective Breakdown Triangle Pair",
                99900,
                "Folding stands with reflective panels and carry case",
            ),
        ),
    },
    "pet_supplies": {
        "brands": ("Pawfern", "Moss & Muzzle", "Tumbletail", "Kindred Kennel"),
        "variants": (
            ("Small", "Oat", 0),
            ("Medium", "Oat", 9000),
            ("Large", "Oat", 18000),
            ("Extra large", "Oat", 28000),
            ("Small", "Juniper", 0),
            ("Medium", "Juniper", 9000),
            ("Large", "Juniper", 18000),
            ("Extra large", "Juniper", 28000),
        ),
        "products": (
            (
                "feeding",
                "Slow-feed Ceramic Bowl",
                89900,
                "Weighted glazed bowl with a removable silicone ring",
            ),
            (
                "walking",
                "Padded Everyday Lead",
                64900,
                "Recycled webbing with a reinforced swivel clip",
            ),
            (
                "grooming",
                "Soft-pin Grooming Brush",
                49900,
                "Rounded stainless pins with a clean-out button",
            ),
            (
                "rest",
                "Washable Bolster Pet Bed",
                249900,
                "Recycled-fiber fill with a removable cover",
            ),
            (
                "enrichment",
                "Treat-dispensing Puzzle Ball",
                59900,
                "Adjustable opening for dry treats and kibble",
            ),
            (
                "travel",
                "Foldable Travel Water Bowl",
                29900,
                "Food-safe silicone with a clip for bags",
            ),
            (
                "litter",
                "Low-dust Natural Cat Litter",
                39900,
                "Plant-fiber granules with no added fragrance",
            ),
            (
                "small animals",
                "Timothy Hay Feeding Rack",
                54900,
                "Coated metal rack with rounded edges",
            ),
            (
                "aquatics",
                "Quiet-flow Aquarium Filter",
                119900,
                "Adjustable flow for tanks up to 60 litres",
            ),
            ("care", "Oatmeal Pet Wash", 69900, "Soap-free wash with colloidal oat and aloe"),
        ),
    },
}

_NEW_PORTFOLIO_FAMILIES: dict[str, dict[str, Any]] = {
    "headphones": {
        "brands": ("Auralis", "Cendre", "Ostera", "Vantrel"),
        "variants": tuple(
            (f"{connection} / {edition}", color, delta)
            for connection, delta in (("Wireless", 0), ("Studio wired", 180000))
            for color in ("Charcoal", "Cloud")
            for edition in ("standard", "travel case")
        ),
        "products": (
            (
                "over-ear",
                "Stilltone Active Headphones",
                849900,
                "adaptive noise control and 42-hour battery",
            ),
            (
                "studio",
                "Reference Fold Headphones",
                629900,
                "closed-back acoustic design with replaceable pads",
            ),
            (
                "commuting",
                "Wayline Travel Headphones",
                579900,
                "fold-flat cups and ambient listening mode",
            ),
            (
                "sports",
                "Paceform Sport Earphones",
                219900,
                "secure-fit hooks and sweat-resistant housing",
            ),
            (
                "open-ear",
                "Openpath Air Headphones",
                399900,
                "open-ear drivers for situational awareness",
            ),
            (
                "on-ear",
                "Daymark On-ear Headphones",
                329900,
                "lightweight frame with a detachable cable",
            ),
            ("wireless", "Quiet Arc Earbuds", 499900, "three-size tips and a pocket charging case"),
            (
                "studio",
                "Mixwell Monitor Headphones",
                739900,
                "balanced response with a coiled reference cable",
            ),
            (
                "gaming",
                "Lantern Voice Headset",
                459900,
                "detachable boom microphone and sidetone control",
            ),
            (
                "accessibility",
                "Clearcall Hearing Headset",
                389900,
                "large tactile controls and amplified voice mode",
            ),
        ),
    },
    "smartwatches": {
        "brands": ("Tavren", "Elowyn", "Mirelle", "Caelus"),
        "variants": tuple(
            (f"{size} / {edition}", color, delta)
            for size, delta in (("40 mm", 0), ("44 mm", 350000))
            for color in ("Slate", "Moss")
            for edition in ("standard band", "two-band set")
        ),
        "products": (
            (
                "everyday",
                "Arcday Connected Watch",
                899900,
                "bright always-on display with replaceable bands",
            ),
            (
                "fitness",
                "Stridefield Fitness Watch",
                1199900,
                "multi-sport tracking and recovery summaries",
            ),
            (
                "outdoor",
                "Northlight Trail Watch",
                1699900,
                "dual-band positioning and a reinforced bezel",
            ),
            (
                "classic",
                "Meridian Round Watch",
                1399900,
                "round OLED display with tactile crown navigation",
            ),
            (
                "compact",
                "Petal Mini Watch",
                799900,
                "compact case with a week of typical battery use",
            ),
            (
                "health",
                "Daywell Wellness Watch",
                1299900,
                "sleep and activity trends with on-device summaries",
            ),
            (
                "hybrid",
                "Stillmark Hybrid Watch",
                1099900,
                "analog hands over a discreet notification display",
            ),
            (
                "water sports",
                "Tidepath Swim Watch",
                1499900,
                "water-resistant case with lap tracking",
            ),
            (
                "accessibility",
                "Clearview Tactile Watch",
                949900,
                "high-contrast display and configurable haptics",
            ),
            (
                "long battery",
                "Longleaf Endurance Watch",
                1249900,
                "low-power display with extended activity tracking",
            ),
        ),
    },
    "tablets": {
        "brands": ("Sorell", "Nivane", "Orlune", "Briarion"),
        "variants": tuple(
            (f"{storage} / {edition}", color, delta)
            for storage, delta in (("128 GB Wi-Fi", 0), ("256 GB Wi-Fi", 450000))
            for color in ("Silver", "Ink")
            for edition in ("standard", "keyboard cover")
        ),
        "products": (
            (
                "study",
                "Notevale 11 Tablet",
                2599000,
                "11-inch display with stylus-ready note taking",
            ),
            (
                "creative",
                "Colorfield Studio Tablet",
                4899000,
                "laminated display tuned for illustration",
            ),
            (
                "reading",
                "Paperlight Reader Tablet",
                1499000,
                "matte low-glare screen with warm reading mode",
            ),
            ("compact", "Pocket Slate Tablet", 1899000, "8.4-inch display for one-handed reading"),
            (
                "family",
                "Hearthside Family Tablet",
                2199000,
                "profile switching with configurable screen time",
            ),
            (
                "business",
                "Ledger Pro Tablet",
                3999000,
                "secure sign-in with keyboard-cover support",
            ),
            (
                "rugged",
                "Fieldnote Rugged Tablet",
                3599000,
                "reinforced frame for workshop and field use",
            ),
            (
                "entertainment",
                "Panorama Media Tablet",
                3299000,
                "quad speakers with a wide color display",
            ),
            (
                "accessibility",
                "Clearpath Easy Tablet",
                1999000,
                "large-text setup and switch-control support",
            ),
            (
                "convertible",
                "Foldline Detachable Tablet",
                4299000,
                "magnetic keyboard cover with adjustable stand",
            ),
        ),
    },
    "cameras": {
        "brands": ("Velmora", "Caelwyn", "Iverna", "Taloris"),
        "variants": tuple(
            (f"{kit} / {edition}", color, delta)
            for kit, delta in (("Body only", 0), ("Kit lens", 850000))
            for color in ("Black", "Silver")
            for edition in ("standard kit", "creator kit")
        ),
        "products": (
            (
                "mirrorless",
                "Lumenfield 24 Camera",
                7299000,
                "24 MP sensor with in-body stabilization",
            ),
            (
                "travel",
                "Wayfarer Compact Camera",
                3899000,
                "one-inch sensor and a retractable zoom lens",
            ),
            (
                "video",
                "Framewell Creator Camera",
                8499000,
                "oversampled 4K recording with a flip screen",
            ),
            (
                "wildlife",
                "Longreach Telephoto Camera",
                9499000,
                "fast subject tracking for distant action",
            ),
            (
                "street",
                "Stillpoint Rangefinder Camera",
                6299000,
                "quiet shutter with direct exposure controls",
            ),
            (
                "instant",
                "Keepsake Instant Camera",
                999900,
                "automatic exposure with credit-card-size prints",
            ),
            (
                "action",
                "Ridgeview Action Camera",
                2599000,
                "wide-angle stabilization in a compact body",
            ),
            (
                "film",
                "Daylight 35 Film Camera",
                1499000,
                "manual focus with a built-in light meter",
            ),
            (
                "document",
                "Cleartext Document Camera",
                1199900,
                "overhead capture with page-edge correction",
            ),
            (
                "studio",
                "Softbox Studio Camera",
                10499000,
                "high-resolution capture with tethered shooting",
            ),
        ),
    },
    "televisions": {
        "brands": ("Orynden", "Kestrelia", "Lumeon", "Sundrel"),
        "variants": tuple(
            (f"{size} / {edition}", color, delta)
            for size, delta in (("43 inch", 0), ("55 inch", 950000))
            for color in ("Charcoal", "Graphite")
            for edition in ("standard panel", "cinema panel")
        ),
        "products": (
            (
                "OLED",
                "Nightglass OLED Television",
                6499000,
                "self-lit pixels with a low-reflection finish",
            ),
            ("QLED", "Brightline QLED Television", 4499000, "quantum-dot color with local dimming"),
            (
                "Mini LED",
                "Sunward Mini LED Television",
                5599000,
                "fine-grained backlight control for bright rooms",
            ),
            (
                "cinema",
                "Wideframe Cinema Television",
                7299000,
                "wide color coverage with a filmmaker picture mode",
            ),
            (
                "gaming",
                "Currentflow Gaming Television",
                5999000,
                "variable refresh input with low-latency mode",
            ),
            (
                "compact",
                "Hearthview Compact Television",
                2499000,
                "small-room display with clear dialogue mode",
            ),
            (
                "art display",
                "Stillroom Art Television",
                8199000,
                "matte panel with an adjustable gallery frame",
            ),
            (
                "outdoor",
                "Terraceview Outdoor Television",
                12999000,
                "weather-resistant enclosure for covered patios",
            ),
            (
                "accessible",
                "Clearvoice Accessible Television",
                3799000,
                "spoken menus and high-contrast captions",
            ),
            (
                "large format",
                "Panorama 75 Television",
                10999000,
                "75-inch panel with a slim wall mount",
            ),
        ),
    },
    "gaming": {
        "brands": ("Emberbyte", "Arcforge", "Tandemix", "Quorrel"),
        "variants": tuple(
            (f"{edition} / {bundle}", color, delta)
            for edition, delta in (("Standard", 0), ("Bundle edition", 450000))
            for color in ("Black", "White")
            for bundle in ("Console only", "with second controller")
        ),
        "products": (
            (
                "console",
                "Emberbyte Living-room Console",
                4999000,
                "quiet cooling with a 1 TB solid-state drive",
            ),
            (
                "handheld",
                "Arcforge Pocket Gaming System",
                3299000,
                "7-inch variable-refresh handheld display",
            ),
            (
                "controller",
                "Tandemix Adaptive Controller",
                699900,
                "remappable controls with two rear paddles",
            ),
            (
                "keyboard",
                "Quorrel Mechanical Gaming Keyboard",
                899900,
                "hot-swappable linear switches and quiet foam",
            ),
            (
                "mouse",
                "Emberbyte Precision Gaming Mouse",
                599900,
                "lightweight shell with adjustable sensitivity",
            ),
            (
                "monitor",
                "Arcforge 27 Gaming Monitor",
                2899000,
                "27-inch 165 Hz display with an adjustable stand",
            ),
            (
                "streaming",
                "Tandemix Capture Station",
                1199900,
                "hardware capture for dual-PC streaming",
            ),
            (
                "simulation",
                "Quorrel Flight Control Set",
                2199900,
                "modular throttle and reversible control stick",
            ),
            (
                "audio",
                "Emberbyte Spatial Headset",
                999900,
                "closed-back drivers with a detachable microphone",
            ),
            (
                "accessibility",
                "Arcforge Switch Gaming Hub",
                849900,
                "three configurable switch inputs and profile memory",
            ),
        ),
    },
    "home_appliances": {
        "brands": ("Morrowen", "Elderglen", "Ruskvale", "Alderwick"),
        "variants": tuple(
            (f"{capacity} / {edition}", color, delta)
            for capacity, delta in (("Standard capacity", 0), ("Extended capacity", 650000))
            for color in ("White", "Graphite")
            for edition in ("standard", "extended filter set")
        ),
        "products": (
            (
                "laundry",
                "Quietwater Front-load Washer",
                3499000,
                "load-sensing wash with a quick cycle",
            ),
            (
                "refrigeration",
                "Hearthwell Bottom-freezer Fridge",
                4299000,
                "separate humidity zones for fresh produce",
            ),
            (
                "floor care",
                "Stillhome Cordless Vacuum",
                1899000,
                "sealed filtration with a removable battery",
            ),
            (
                "air care",
                "Clearfield Room Air Purifier",
                1599000,
                "replaceable particle and odor filters",
            ),
            (
                "climate",
                "Morrowen Inverter Air Conditioner",
                3699000,
                "variable-speed cooling with a washable filter",
            ),
            (
                "water",
                "Springwell Countertop Filter",
                1299000,
                "replaceable carbon filter with a change indicator",
            ),
            (
                "dish care",
                "Alderwick Compact Dishwasher",
                2999000,
                "place settings for smaller kitchens",
            ),
            (
                "heating",
                "Elderglen Ceramic Room Heater",
                799900,
                "tip-over shutoff and adjustable thermostat",
            ),
            (
                "laundry",
                "Ruskvale Heat-pump Dryer",
                3899000,
                "sensor drying with a low-temperature cycle",
            ),
            (
                "air care",
                "Breezefield Tower Fan",
                899900,
                "quiet airflow with a timed sleep setting",
            ),
        ),
    },
}

CATALOG_FAMILIES = {
    "laptops": _SOURCE_CATALOG_FAMILIES["laptops"],
    "smartphones": _SOURCE_CATALOG_FAMILIES["phones"],
    "headphones": _NEW_PORTFOLIO_FAMILIES["headphones"],
    "smartwatches": _NEW_PORTFOLIO_FAMILIES["smartwatches"],
    "tablets": _NEW_PORTFOLIO_FAMILIES["tablets"],
    "cameras": _NEW_PORTFOLIO_FAMILIES["cameras"],
    "televisions": _NEW_PORTFOLIO_FAMILIES["televisions"],
    "gaming": _NEW_PORTFOLIO_FAMILIES["gaming"],
    "home_appliances": _NEW_PORTFOLIO_FAMILIES["home_appliances"],
    "kitchen_appliances": _SOURCE_CATALOG_FAMILIES["appliances"],
    "fashion": _SOURCE_CATALOG_FAMILIES["fashion"],
    "footwear": _SOURCE_CATALOG_FAMILIES["footwear"],
    "beauty": _SOURCE_CATALOG_FAMILIES["beauty"],
    "accessories": _SOURCE_CATALOG_FAMILIES["accessories"],
    "home_living": _SOURCE_CATALOG_FAMILIES["home"],
}
CATALOG_FAMILIES = aligned_families(CATALOG_FAMILIES)

CATALOG_CATEGORIES = tuple(CATALOG_FAMILIES)
PRODUCTS_PER_CATEGORY = 80
CATALOG_SIZE = len(CATALOG_CATEGORIES) * PRODUCTS_PER_CATEGORY
_ASSET_ROOT = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "public"
    / "images"
    / "products"
    / "portfolio"
)
_ASSET_MANIFEST = json.loads((_ASSET_ROOT / "manifest.json").read_text(encoding="utf-8"))
_ASSET_HASHES = {image["file"]: image["sha256"] for image in _ASSET_MANIFEST["images"]}

_HERO_LAPTOP_IMAGES = {
    1: ("laptops/hero/vellune-studybook-hero.png", "laptops/hero/vellune-studybook-alt.png"),
    5: ("laptops/hero/vellune-copperfield-hero.png", "laptops/hero/vellune-copperfield-alt.png"),
    6: (
        "laptops/hero/merroway-featherweight-hero.png",
        "laptops/hero/merroway-featherweight-alt.png",
    ),
}


class CatalogSeedSafetyError(ValueError):
    """The requested catalog seed target is not explicitly allowlisted."""


class CatalogSeedCollisionError(ValueError):
    """A reserved catalog identity belongs to an unexpected product."""


def build_catalog_products() -> list[Product]:
    """Build 80 stable, varied product variants for each canonical family."""
    products: list[Product] = []
    for category, family in CATALOG_FAMILIES.items():
        for product_index, (subcategory, title, base_price, feature) in enumerate(
            family["products"], start=1
        ):
            brand = family["brands"][(product_index - 1) % len(family["brands"])]
            for variant_index in range(1, 9):
                archetype = (product_index - 1) % 5
                variant, price_delta, configuration = product_configuration(
                    category, archetype, variant_index - 1
                )
                sku = f"PORT-{category.upper()}-{product_index:02d}-{variant_index:02d}"
                price = base_price + price_delta
                hero_images = (
                    _HERO_LAPTOP_IMAGES.get(product_index) if category == "laptops" else None
                )
                image_path = (
                    hero_images[0]
                    if hero_images
                    else f"{category}/{(product_index - 1) % 5 + 1:02d}.jpg"
                )
                image_url = f"/images/products/portfolio/{image_path}"
                name = f"{brand} {title}, {variant}"
                specifications: dict[str, Any] = {
                    "Subcategory": subcategory,
                    "Variant": variant,
                    "Key details": feature,
                    **configuration,
                    "Image note": "Illustrative portfolio-family product photography; the pictured scene is not a claim about a specific SKU.",
                    "_presentation": {
                        "delivery": "Standard portfolio delivery; timing confirmed at checkout",
                        "highlights": [
                            feature,
                            variant,
                            "Illustrative portfolio-family studio photograph",
                        ],
                        "image_gallery": (
                            [
                                {
                                    "url": image_url,
                                    "alt": f"Premium studio view of {name}",
                                    "role": "hero",
                                },
                                {
                                    "url": f"/images/products/portfolio/{hero_images[1]}",
                                    "alt": f"Alternate studio view of {name}",
                                    "role": "alternate",
                                },
                            ]
                            if hero_images
                            else [
                                {
                                    "url": image_url,
                                    "alt": f"Studio product photograph illustrating the {category.replace('_', ' ')} product family",
                                }
                            ]
                        ),
                    },
                }
                products.append(
                    Product(
                        id=uuid5(NAMESPACE_URL, f"shopsmart/{CATALOG_VERSION}/{sku}"),
                        sku=sku,
                        name=name,
                        description=f"{title} features {feature}.",
                        category=category,
                        brand=brand,
                        price=price,
                        list_price=(
                            price
                            + max(
                                5000,
                                round(
                                    price * (0.05 + ((product_index + variant_index) % 17) / 100)
                                ),
                            )
                            if (product_index + variant_index) % 4
                            else None
                        ),
                        stock_quantity=(
                            0
                            if product_index == 10 and variant_index == 8
                            else 1 + (product_index * 11 + variant_index * 17) % 73
                        ),
                        specifications=specifications,
                        image_url=image_url,
                        image_alt=f"Studio product photograph illustrating the {category.replace('_', ' ')} product family",
                        image_source_url=image_url,
                        image_creator="OpenAI built-in image_gen, commissioned for the ShopSmart portfolio",
                        image_license="Repository-created AI-generated portfolio-family image",
                        image_license_url=None,
                        image_sha256=_ASSET_HASHES[image_path],
                        max_purchase_quantity=5,
                        is_active=True,
                    )
                )
    return products


def validate_catalog_target(
    apply: bool,
    environment: dict[str, str],
    database_url: str,
) -> None:
    if not apply or environment.get(CATALOG_OPT_IN) != "true":
        raise CatalogSeedSafetyError(f"Pass --apply and set {CATALOG_OPT_IN}=true.")
    if environment.get("SHOPSMART_ENV", "").strip().lower() not in LOCAL_ENVIRONMENTS:
        raise CatalogSeedSafetyError("Set SHOPSMART_ENV to local, development, or test.")
    if any(
        environment.get(variable, "").strip().lower() in PRODUCTION_ENVIRONMENTS
        for variable in ("APP_ENV", "ENVIRONMENT", "NODE_ENV")
    ):
        raise CatalogSeedSafetyError(
            "Catalog fixture seeding is forbidden in production-like environments."
        )
    try:
        database = make_url(database_url)
    except Exception as error:
        raise CatalogSeedSafetyError("The database target is invalid.") from error
    if not database.drivername.startswith("postgresql") or database.database != CATALOG_DATABASE:
        raise CatalogSeedSafetyError(f"Use only the dedicated {CATALOG_DATABASE} database.")
    hosts = [host for host in (database.host, database.query.get("host")) if host]
    if not hosts or any(host not in {"localhost", "127.0.0.1", "::1"} for host in hosts):
        raise CatalogSeedSafetyError("Catalog fixture seeding requires an explicit loopback host.")


async def seed_catalog_products(session: AsyncSession) -> dict[str, int]:
    """Insert missing fixture rows; never update or delete an existing product."""
    products = build_catalog_products()
    product_ids = {product.id: product for product in products}
    product_skus = {product.sku: product for product in products}
    existing = (
        (
            await session.execute(
                select(Product).where(
                    or_(Product.id.in_(product_ids), Product.sku.in_(product_skus))
                )
            )
        )
        .scalars()
        .all()
    )
    by_id = {product.id: product for product in existing}
    by_sku = {product.sku: product for product in existing}
    pending = []
    already_seeded = 0

    for fixture in products:
        row_by_id = by_id.get(fixture.id)
        row_by_sku = by_sku.get(fixture.sku)
        if row_by_id is None and row_by_sku is None:
            pending.append(fixture)
            continue
        if row_by_id is not row_by_sku:
            raise CatalogSeedCollisionError("A reserved product ID or SKU belongs to other data.")
        already_seeded += 1

    session.add_all(pending)
    await session.flush()
    return {"inserted": len(pending), "already_present": already_seeded}


async def repair_catalog_products(session: AsyncSession) -> dict[str, int]:
    """Refresh authored portfolio metadata only when both reserved identities agree.

    Order item snapshots remain untouched. Existing carts will receive the current
    catalog price through CartService, exactly as they do after an inventory update.
    """
    authored = build_catalog_products()
    rows = (
        (
            await session.execute(
                select(Product).where(
                    or_(
                        Product.id.in_([p.id for p in authored]),
                        Product.sku.in_([p.sku for p in authored]),
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    by_id = {row.id: row for row in rows}
    by_sku = {row.sku: row for row in rows}
    fields = (
        "name",
        "description",
        "category",
        "brand",
        "price",
        "list_price",
        "specifications",
        "image_url",
        "image_alt",
        "image_source_url",
        "image_creator",
        "image_license",
        "image_license_url",
        "image_sha256",
    )
    updated = 0
    for product in authored:
        row = by_id.get(product.id)
        sku_row = by_sku.get(product.sku)
        if row is None and sku_row is None:
            continue
        if row is not sku_row:
            raise CatalogSeedCollisionError("A reserved product ID or SKU belongs to other data.")
        for field in fields:
            setattr(row, field, getattr(product, field))
        updated += 1
    await session.flush()
    return {"updated": updated}


async def _run_seed(database_url: str, repair: bool = False) -> dict[str, int]:
    engine = create_async_engine(database_url)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            async with session.begin():
                result = (
                    await repair_catalog_products(session)
                    if repair
                    else await seed_catalog_products(session)
                )
        return result
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Refresh reserved local portfolio metadata without changing IDs, stock or orders",
    )
    args = parser.parse_args(argv)
    environment = dict(os.environ)
    database_url = environment.get("DATABASE_URL", "")
    try:
        validate_catalog_target(args.apply, environment, database_url)
    except CatalogSeedSafetyError as error:
        print(f"Catalog fixture seed refused; no changes made. {error}")
        return 2

    try:
        result = asyncio.run(_run_seed(database_url, args.repair))
    except CatalogSeedCollisionError as error:
        print(f"Catalog fixture seed refused; no changes made. {error}")
        return 2
    except Exception as error:
        print(
            f"Catalog fixture seed failed ({type(error).__name__}); database details were suppressed.",
            file=sys.stderr,
        )
        return 1
    print(f"Applied {CATALOG_VERSION}: {result}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
