"""
Product catalog (with SCD Type 2 cost history) and US geography dimension.

Two things worth noting for a reviewer:

1. Unit cost is *versioned*, not a single current value. Applying today's cost
   to a 2023 order would silently rewrite history. The order generator looks up
   the cost version valid on the order date.

2. Shipping zones are computed from a single fulfillment center in Columbus, OH.
   That is what makes geography an economic variable rather than a map color.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C

# --------------------------------------------------------------------------
# Product name vocabulary -- deterministic, so SKUs are stable across runs
# --------------------------------------------------------------------------
_PREFIX = {
    "Outerwear": ["Alpine", "Summit", "Ridgeline", "Northwind", "Cascade", "Timberline"],
    "Tops": ["Basecamp", "Trailhead", "Meridian", "Fieldstone", "Harbor", "Drifter"],
    "Bottoms": ["Granite", "Switchback", "Junction", "Bedrock", "Portage"],
    "Footwear": ["Traverse", "Bootjack", "Scree", "Talus", "Foothill"],
    "Accessories": ["Waypoint", "Compass", "Lakeshore", "Cinder", "Quarry", "Beacon"],
    "Bags": ["Overland", "Haulback", "Expedition", "Rucksack", "Carryall"],
}
_SUFFIX = {
    "Outerwear": ["Insulated Jacket", "Shell Parka", "Down Vest", "Fleece Jacket",
                  "3-in-1 Coat", "Windbreaker"],
    "Tops": ["Merino Tee", "Flannel Shirt", "Henley", "Crew Sweatshirt",
             "Sun Hoodie", "Base Layer"],
    "Bottoms": ["Hiking Pant", "Utility Short", "Lined Jean", "Trail Jogger",
                "Convertible Pant"],
    "Footwear": ["Trail Runner", "Hiking Boot", "Approach Shoe", "Camp Slipper",
                 "Waterproof Mid"],
    "Accessories": ["Beanie", "Trucker Cap", "Merino Socks", "Leather Belt",
                    "Neck Gaiter", "Liner Glove"],
    "Bags": ["Daypack", "Duffel", "Sling Bag", "Tote", "Travel Pack"],
}


def build_products(rng: np.random.Generator) -> pd.DataFrame:
    """One row per SKU *version*. Natural key = sku, surrogate key = product_key."""
    rows = []
    sku_seq = 0

    for category, (share, p_min, p_max, cost_ratio, w_min, w_max, ret) in C.CATEGORIES.items():
        n = max(1, round(C.N_SKUS * share))
        for i in range(n):
            sku_seq += 1
            sku = f"NL-{category[:3].upper()}-{sku_seq:04d}"

            # Price follows a right-skewed distribution inside the category band
            u = rng.beta(2.0, 3.2)
            list_price = round(p_min + u * (p_max - p_min), 2)

            name = (f"{_PREFIX[category][i % len(_PREFIX[category])]} "
                    f"{_SUFFIX[category][(i // 3) % len(_SUFFIX[category])]}")
            if i >= len(_PREFIX[category]):
                name += f" {['II', 'Pro', 'Lite', 'HD', 'XT'][i % 5]}"

            rows.append({
                "sku": sku,
                "product_name": name,
                "category": category,
                "list_price": list_price,
                "base_cost_ratio": cost_ratio,
                "weight_lbs": round(rng.uniform(w_min, w_max), 2),
                "baseline_return_rate": ret,
                "launch_rank": i,
            })

    products = pd.DataFrame(rows)

    # ---- Popularity: power law, so a few heroes carry the catalog --------
    raw_pop = rng.pareto(C.SKU_POPULARITY_ALPHA, len(products)) + 1.0
    products["demand_weight"] = raw_pop / raw_pop.sum()

    # ---- Finding 1: plant the two defective Outerwear SKUs -----------------
    outer = products.index[products["category"] == C.DEFECT_SKU_CATEGORY]
    defect_idx = rng.choice(outer, size=C.DEFECT_SKU_COUNT, replace=False)

    products["is_defect_sku"] = False
    products.loc[defect_idx, "is_defect_sku"] = True
    products.loc[defect_idx, "baseline_return_rate"] = C.DEFECT_RETURN_RATE
    products.loc[defect_idx, "base_cost_ratio"] = C.DEFECT_COST_RATIO
    products.loc[defect_idx, "demand_weight"] *= C.DEFECT_DEMAND_MULTIPLIER
    products["demand_weight"] /= products["demand_weight"].sum()

    # Give them plausible bestseller pricing in the mid band
    products.loc[defect_idx, "list_price"] = [
        round(x, 2) for x in rng.uniform(139.0, 168.0, C.DEFECT_SKU_COUNT)
    ]

    return _explode_cost_history(products, rng)


def _explode_cost_history(products: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Turn one row per SKU into one row per SKU-cost-version (SCD Type 2)."""
    versions = []
    boundaries = [C.START_DATE] + list(C.COST_CHANGE_DATES) + [None]

    for _, p in products.iterrows():
        cost = p["list_price"] * p["base_cost_ratio"]
        for v in range(len(boundaries) - 1):
            if v > 0:
                cost *= 1.0 + rng.uniform(*C.COST_CHANGE_RANGE)
            valid_to = boundaries[v + 1]
            versions.append({
                "product_key": f"{p['sku']}-V{v + 1}",
                "sku": p["sku"],
                "product_name": p["product_name"],
                "category": p["category"],
                "list_price": p["list_price"],
                "unit_cost": round(cost, 2),
                "weight_lbs": p["weight_lbs"],
                "baseline_return_rate": p["baseline_return_rate"],
                "demand_weight": p["demand_weight"],
                "is_defect_sku": p["is_defect_sku"],
                "valid_from": boundaries[v],
                "valid_to": None if valid_to is None else valid_to - pd.Timedelta(days=1).to_pytimedelta(),
                "is_current": valid_to is None,
            })

    return pd.DataFrame(versions)


# --------------------------------------------------------------------------
# Geography
# state -> (name, census_region, census_division, shipping_zone, population_m)
# Zones measured from the Columbus, OH fulfillment center.
# --------------------------------------------------------------------------
_STATES = {
    "OH": ("Ohio", "Midwest", "East North Central", 2, 11.8),
    "IN": ("Indiana", "Midwest", "East North Central", 2, 6.9),
    "KY": ("Kentucky", "South", "East South Central", 2, 4.5),
    "WV": ("West Virginia", "South", "South Atlantic", 2, 1.8),
    "PA": ("Pennsylvania", "Northeast", "Middle Atlantic", 3, 13.0),
    "MI": ("Michigan", "Midwest", "East North Central", 3, 10.0),
    "IL": ("Illinois", "Midwest", "East North Central", 3, 12.5),
    "WI": ("Wisconsin", "Midwest", "East North Central", 3, 5.9),
    "TN": ("Tennessee", "South", "East South Central", 3, 7.1),
    "VA": ("Virginia", "South", "South Atlantic", 3, 8.7),
    "NY": ("New York", "Northeast", "Middle Atlantic", 3, 19.6),
    "NJ": ("New Jersey", "Northeast", "Middle Atlantic", 3, 9.3),
    "MD": ("Maryland", "South", "South Atlantic", 3, 6.2),
    "NC": ("North Carolina", "South", "South Atlantic", 3, 10.8),
    "DE": ("Delaware", "South", "South Atlantic", 3, 1.0),
    "DC": ("District of Columbia", "South", "South Atlantic", 3, 0.7),
    "SC": ("South Carolina", "South", "South Atlantic", 4, 5.4),
    "GA": ("Georgia", "South", "South Atlantic", 4, 11.0),
    "AL": ("Alabama", "South", "East South Central", 4, 5.1),
    "MS": ("Mississippi", "South", "East South Central", 4, 2.9),
    "MO": ("Missouri", "Midwest", "West North Central", 4, 6.2),
    "IA": ("Iowa", "Midwest", "West North Central", 4, 3.2),
    "MN": ("Minnesota", "Midwest", "West North Central", 4, 5.7),
    "AR": ("Arkansas", "South", "West South Central", 4, 3.1),
    "LA": ("Louisiana", "South", "West South Central", 4, 4.6),
    "MA": ("Massachusetts", "Northeast", "New England", 4, 7.0),
    "CT": ("Connecticut", "Northeast", "New England", 4, 3.6),
    "RI": ("Rhode Island", "Northeast", "New England", 4, 1.1),
    "NH": ("New Hampshire", "Northeast", "New England", 4, 1.4),
    "VT": ("Vermont", "Northeast", "New England", 4, 0.6),
    "ME": ("Maine", "Northeast", "New England", 4, 1.4),
    "FL": ("Florida", "South", "South Atlantic", 5, 22.6),
    "TX": ("Texas", "South", "West South Central", 5, 30.5),
    "OK": ("Oklahoma", "South", "West South Central", 5, 4.1),
    "KS": ("Kansas", "Midwest", "West North Central", 5, 2.9),
    "NE": ("Nebraska", "Midwest", "West North Central", 5, 2.0),
    "SD": ("South Dakota", "Midwest", "West North Central", 5, 0.9),
    "ND": ("North Dakota", "Midwest", "West North Central", 5, 0.8),
    "CO": ("Colorado", "West", "Mountain", 6, 5.9),
    "NM": ("New Mexico", "West", "Mountain", 6, 2.1),
    "WY": ("Wyoming", "West", "Mountain", 6, 0.6),
    "MT": ("Montana", "West", "Mountain", 6, 1.1),
    "UT": ("Utah", "West", "Mountain", 6, 3.4),
    "AZ": ("Arizona", "West", "Mountain", 7, 7.4),
    "ID": ("Idaho", "West", "Mountain", 7, 2.0),
    "NV": ("Nevada", "West", "Mountain", 7, 3.2),
    "OR": ("Oregon", "West", "Pacific", 7, 4.2),
    "WA": ("Washington", "West", "Pacific", 7, 7.8),
    "CA": ("California", "West", "Pacific", 8, 39.0),
    "AK": ("Alaska", "West", "Pacific", 8, 0.7),
    "HI": ("Hawaii", "West", "Pacific", 8, 1.4),
}

# States with no statewide sales tax -> no economic nexus obligation.
# (Alaska has local-level taxes only; modeled as no state threshold.)
_NO_SALES_TAX = {"OR", "MT", "NH", "DE", "AK"}

# Higher economic-nexus thresholds. Everything else defaults to $100k.
# Reference point: South Dakota v. Wayfair (2018). Flag is a business
# modeling attribute -- not tax advice. See docs/business_rules.md.
_NEXUS_500K = {"CA", "TX", "NY"}


def build_geography() -> pd.DataFrame:
    rows = []
    for code, (name, region, division, zone, pop) in _STATES.items():
        has_tax = code not in _NO_SALES_TAX
        rows.append({
            "geography_key": code,
            "state_code": code,
            "state_name": name,
            "census_region": region,
            "census_division": division,
            "shipping_zone": zone,
            "population_millions": pop,
            "has_state_sales_tax": has_tax,
            "nexus_threshold_usd": (
                None if not has_tax else (500_000 if code in _NEXUS_500K else 100_000)
            ),
        })

    geo = pd.DataFrame(rows)
    # Outdoor apparel over-indexes in the Mountain and Pacific divisions.
    affinity = geo["census_division"].map(
        {"Mountain": 1.55, "Pacific": 1.30, "New England": 1.25,
         "East North Central": 1.05, "West North Central": 1.05}
    ).fillna(0.90)
    w = geo["population_millions"] * affinity
    geo["demand_weight"] = w / w.sum()
    return geo


def outbound_shipping_cost(zone: np.ndarray, weight_lbs: np.ndarray) -> np.ndarray:
    base = C.SHIP_BASE_INTERCEPT + C.SHIP_BASE_PER_ZONE * zone
    rate = C.SHIP_RATE_INTERCEPT + C.SHIP_RATE_PER_ZONE * zone
    return np.round(base + rate * weight_lbs, 2)


def return_shipping_cost(zone: np.ndarray) -> np.ndarray:
    return np.round(C.RETURN_SHIP_BASE + C.RETURN_SHIP_PER_ZONE * zone, 2)
