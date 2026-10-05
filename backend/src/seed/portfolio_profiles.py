"""Fictional portfolio merchandise aligned to the five original drawings per family.

These are authored database seed records, not live commercial claims. The image
index is an explicit domain relationship rather than a category fallback in React.
"""

# Order matches frontend/scripts/portfolio-art/generate.py DRAW exactly.
ART_PROFILES = {
    "laptops": (
        (
            "everyday notebooks",
            "Studybook Laptop",
            4899000,
            "14-inch IPS display and full-size keyboard",
        ),
        (
            "gaming notebooks",
            "Thermal Ridge Gaming Laptop",
            8999000,
            "15.6-inch display, dedicated graphics and backlit keyboard",
        ),
        (
            "convertible notebooks",
            "Foldline Convertible Laptop",
            6499000,
            "touch display with pen support and a folding hinge",
        ),
        (
            "travel notebooks",
            "Featherweight Slim Laptop",
            5599000,
            "14-inch display and a slim metal chassis",
        ),
        (
            "business notebooks",
            "Copperfield Office Laptop",
            5199000,
            "textured copper-finish lid and privacy webcam shutter",
        ),
    ),
    "smartphones": (
        (
            "everyday smartphones",
            "Daylight Smartphone",
            1799000,
            "6.4-inch display with a centered front camera",
        ),
        (
            "camera smartphones",
            "Prism Camera Phone",
            2899000,
            "triple rear cameras and a 6.5-inch display",
        ),
        (
            "foldable smartphones",
            "Foldspace Phone",
            7999000,
            "book-style folding display and reinforced hinge",
        ),
        (
            "everyday smartphones",
            "Meadow Smartphone",
            2299000,
            "dual rear cameras and a 6.3-inch display",
        ),
        (
            "rugged smartphones",
            "Fieldline Rugged Phone",
            2599000,
            "reinforced housing and physical shortcut controls",
        ),
    ),
    "headphones": (
        (
            "over-ear audio",
            "Cloudrest Headphones",
            699900,
            "padded over-ear cups and an adjustable headband",
        ),
        (
            "wireless earbuds",
            "Pocketbuds Earbuds",
            349900,
            "wireless earbuds with a compact charging case",
        ),
        (
            "neckband audio",
            "Trailband Earphones",
            249900,
            "flexible neckband with in-ear silicone tips",
        ),
        ("gaming audio", "Arcwave Gaming Headset", 599900, "over-ear cups with a boom microphone"),
        (
            "over-ear audio",
            "Timbernote Headphones",
            899900,
            "wood-finish earcups and a padded headband",
        ),
    ),
    "smartwatches": (
        (
            "everyday wearables",
            "Daytrack Smartwatch",
            699900,
            "touch display with a silicone strap",
        ),
        (
            "round wearables",
            "Orbit Round Smartwatch",
            899900,
            "round display and an adjustable strap",
        ),
        (
            "fitness wearables",
            "Trailmark Fitness Watch",
            799900,
            "activity tracking and a sport strap",
        ),
        (
            "classic wearables",
            "Quiettime Smartwatch",
            1099900,
            "classic watch face with connected notifications",
        ),
        (
            "outdoor wearables",
            "Fieldtrack Sport Watch",
            1199900,
            "reinforced case and easy-access side controls",
        ),
    ),
    "tablets": (
        ("desk tablets", "Deskscreen Tablet", 2499000, "landscape display with a desktop stand"),
        (
            "drawing tablets",
            "Sketchleaf Pen Tablet",
            3499000,
            "portrait touch display and an included stylus",
        ),
        (
            "everyday tablets",
            "Meadow Slate Tablet",
            2199000,
            "slim metal housing and dual rear cameras",
        ),
        (
            "keyboard tablets",
            "Workfold Keyboard Tablet",
            3999000,
            "landscape display with a detachable keyboard",
        ),
        (
            "reading tablets",
            "Paperlight Reading Tablet",
            1599000,
            "paper-style reading display with page controls",
        ),
    ),
    "cameras": (
        (
            "interchangeable-lens cameras",
            "Framecraft Camera",
            6499000,
            "interchangeable lens mount with a textured handgrip",
        ),
        (
            "compact cameras",
            "Silverline Compact Camera",
            3999000,
            "compact body with a fixed lens and control dial",
        ),
        (
            "compact cameras",
            "Sandstone Travel Camera",
            2999000,
            "lightweight fixed-lens body with built-in flash",
        ),
        (
            "action cameras",
            "Trailframe Action Camera",
            1899000,
            "reinforced housing with a mounting bracket",
        ),
        (
            "instant cameras",
            "Mintframe Instant Camera",
            999900,
            "instant print slot and a built-in flash",
        ),
    ),
    "televisions": (
        ("smart televisions", "Horizon Smart TV", 2999000, "wide display with two supporting feet"),
        (
            "smart televisions",
            "Panorama Smart TV",
            3999000,
            "wide display with a central pedestal stand",
        ),
        (
            "smart televisions",
            "Wallline Smart TV",
            4499000,
            "slim display with wall-mount compatibility",
        ),
        (
            "smart televisions",
            "Cinemafield Smart TV",
            4999000,
            "wide display with a stable desktop stand",
        ),
        (
            "smart televisions",
            "Studioframe Smart TV",
            5499000,
            "display designed for a media-room setup",
        ),
    ),
    "gaming": (
        (
            "controllers",
            "Arcwave Wireless Controller",
            399900,
            "dual thumbsticks and shoulder triggers",
        ),
        (
            "handheld consoles",
            "Pocketarc Handheld Console",
            2499000,
            "integrated display with dual thumbstick controls",
        ),
        (
            "virtual reality",
            "Vista VR Headset",
            3499000,
            "head-mounted display with two motion controllers",
        ),
        (
            "arcade systems",
            "Pixelhall Arcade Cabinet",
            5499000,
            "cabinet display with joystick and button controls",
        ),
        (
            "gaming keyboards",
            "Glowkey Gaming Keyboard",
            499900,
            "illuminated keycaps and a full desktop layout",
        ),
    ),
    "home_appliances": (
        (
            "laundry",
            "Quietwater Front-load Washer",
            3499000,
            "front-loading drum with adjustable wash programs",
        ),
        (
            "refrigeration",
            "Hearthwell Fridge",
            4299000,
            "separate chilled and frozen storage compartments",
        ),
        (
            "floor care",
            "Stillhome Robot Vacuum",
            1899000,
            "round low-profile body with automatic floor cleaning",
        ),
        (
            "air care",
            "Clearfield Air Purifier",
            1599000,
            "replaceable particle filter and adjustable fan modes",
        ),
        (
            "air care",
            "Breezefield Pedestal Fan",
            499900,
            "adjustable height with a protective blade guard",
        ),
    ),
    "kitchen_appliances": (
        (
            "toasters",
            "Morningfold Toaster",
            299900,
            "two bread slots with adjustable browning controls",
        ),
        (
            "blenders",
            "Freshwhirl Blender",
            449900,
            "removable blending jar with graduated markings",
        ),
        (
            "kettles",
            "Steepwell Electric Kettle",
            199900,
            "cordless pouring jug with an automatic shutoff",
        ),
        (
            "coffee makers",
            "Brewfield Coffee Maker",
            699900,
            "countertop brewer with a removable water reservoir",
        ),
        ("stand mixers", "Bakewell Stand Mixer", 1299900, "mixing bowl with tilt-head access"),
    ),
    "fashion": (
        ("t-shirts", "Softline Cotton T-shirt", 79900, "crew neckline and soft cotton jersey"),
        ("dresses", "Dayfield Midi Dress", 189900, "flowing skirt and a comfortable waist seam"),
        ("jackets", "Fieldline Zip Jacket", 249900, "zip front with practical side pockets"),
        (
            "jeans",
            "Everyday Straight Jeans",
            199900,
            "straight-leg denim with a classic five-pocket layout",
        ),
        (
            "hoodies",
            "Cloudrest Pullover Hoodie",
            169900,
            "drawstring hood and a front kangaroo pocket",
        ),
    ),
    "footwear": (
        ("sneakers", "Daywalk Casual Sneakers", 249900, "lace-up upper with a cushioned sole"),
        ("boots", "Fieldstep Ankle Boots", 399900, "ankle-height upper with a textured outsole"),
        ("heels", "Eveningline Dress Heels", 299900, "closed-toe upper with a raised heel"),
        ("sandals", "Suntrail Open Sandals", 149900, "open straps and a comfortable footbed"),
        (
            "running shoes",
            "Swiftstride Running Shoes",
            349900,
            "breathable upper and a cushioned running sole",
        ),
    ),
    "beauty": (
        ("lip color", "Velvetline Lipstick", 59900, "twist-up lip color with a smooth finish"),
        ("fragrance", "Meadowlight Eau de Parfum", 199900, "spray fragrance in a glass bottle"),
        ("skin care", "Softcloud Face Cream", 89900, "face moisturizer in a reusable glass jar"),
        ("face makeup", "Dayglow Powder Compact", 79900, "pressed powder with a mirrored compact"),
        (
            "nail color",
            "Petalshine Nail Polish",
            39900,
            "brush-applicator nail color in a glass bottle",
        ),
    ),
    "accessories": (
        ("eyewear", "Sunfield Sunglasses", 129900, "tinted lenses with a lightweight frame"),
        (
            "backpacks",
            "Trailpack Everyday Backpack",
            199900,
            "zippered main compartment with padded straps",
        ),
        ("wallets", "Foldline Card Wallet", 79900, "compact folding design with card pockets"),
        ("belts", "Everyday Buckle Belt", 99900, "adjustable strap with a metal buckle"),
        ("caps", "Daytrail Baseball Cap", 59900, "curved peak and an adjustable rear closure"),
    ),
    "home_living": (
        ("lighting", "Quietglow Table Lamp", 249900, "shaded tabletop lamp with a stable base"),
        (
            "seating",
            "Cloudline Living Sofa",
            3499900,
            "upholstered seating with supportive cushions",
        ),
        (
            "decor",
            "Meadowpot Decorative Plant",
            199900,
            "artificial leafy plant in a decorative pot",
        ),
        ("clocks", "Stilltime Wall Clock", 149900, "round analog face with clear hour markers"),
        (
            "storage",
            "Openline Display Shelf",
            899900,
            "open shelving for books and small home objects",
        ),
    ),
}


def aligned_families(existing: dict) -> dict:
    """Preserve 80 identities per category while aligning each archetype to its art."""
    return {
        category: {
            **existing[category],
            "products": tuple(
                (subcategory, f"{title} {edition}", price + premium, feature)
                for edition, premium in (("Essential", 0), ("Signature", 5000))
                for subcategory, title, price, feature in profiles
            ),
        }
        for category, profiles in ART_PROFILES.items()
    }


def product_configuration(category: str, archetype: int, index: int) -> tuple[str, int, dict]:
    """Return one of eight coherent authored configurations and its price increment."""
    bundle = "Item only" if index % 2 == 0 else "Care kit included"
    tier = index // 2
    if category == "laptops":
        ram, storage, extra = (
            (8, "256 GB SSD", 0),
            (16, "512 GB SSD", 650000),
            (16, "1 TB SSD", 1450000),
            (32, "1 TB SSD", 2950000),
        )[tier]
        spec = {
            "RAM": f"{ram} GB RAM",
            "Storage": storage,
            "Graphics": "Dedicated graphics" if archetype == 1 else "Integrated graphics",
            "Processor": "6-core processor",
            "Display": "15.6-inch" if archetype == 1 else "14-inch",
        }
        return f"{ram} GB RAM / {storage} / {bundle}", extra + index % 2 * 15000, spec
    if category in {"smartphones", "tablets", "gaming"}:
        if category == "gaming" and archetype != 1:
            options = ("Standard kit", "Extended cable kit", "Travel kit", "Desk kit")
            return (
                f"{options[tier]} / {bundle}",
                tier * 10000 + index % 2 * 5000,
                {"Package": options[tier], "Bundle": bundle},
            )
        storage = (64, 128, 256, 512)[tier]
        return (
            f"{storage} GB storage / {bundle}",
            tier * 150000 + index % 2 * 15000,
            {"Storage": f"{storage} GB", "Bundle": bundle},
        )
    if category == "fashion":
        size = ("XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL")[index]
        return size, 0, {"Size": size, "Care": "Follow the care label"}
    if category == "footwear":
        size = index + 3
        return f"UK {size}", 0, {"Size": f"UK {size}", "Fit": "Standard width"}
    if category == "beauty":
        options = ("Single", "Duo", "Trio", "Gift set")
        finish = "Original" if index % 2 == 0 else "Travel packaging"
        return (
            f"{options[tier]} / {finish}",
            tier * 20000 + index % 2 * 5000,
            {"Package": options[tier], "Presentation": finish},
        )
    if category == "televisions":
        size = (32, 43, 50, 55)[tier]
        return (
            f"{size}-inch / {bundle}",
            tier * 500000 + index % 2 * 15000,
            {
                "Display": f"{size}-inch",
                "Resolution": "Full HD" if tier == 0 else "4K",
                "Bundle": bundle,
            },
        )
    extras = ("Base package", "Storage cover", "Cleaning set", "Cover and cleaning set")
    return (
        f"{extras[tier]} / {bundle}",
        tier * 5000 + index % 2 * 2500,
        {"Package": extras[tier], "Bundle": bundle},
    )
