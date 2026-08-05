"""
Central configuration for the Northlane Supply Co. synthetic dataset.

Every magic number in this project lives here. Nothing is hard-coded downstream.
If a reviewer asks "where does the 2.9% payment fee come from?", the answer is
one file, one line, with a comment.
"""

from __future__ import annotations

import datetime as dt

# --------------------------------------------------------------------------
# Reproducibility
# --------------------------------------------------------------------------
SEED = 42

# --------------------------------------------------------------------------
# Time window
# --------------------------------------------------------------------------
START_DATE = dt.date(2023, 1, 1)
END_DATE = dt.date(2025, 12, 31)

# --------------------------------------------------------------------------
# Business scale
# New customers acquired per calendar year. Drives everything downstream.
# --------------------------------------------------------------------------
NEW_CUSTOMERS_PER_YEAR = {2023: 14_000, 2024: 24_000, 2025: 34_000}

# Monthly seasonality multiplier applied to acquisition and repeat demand.
# Outerwear brand: Q4 peak, February trough.
MONTH_SEASONALITY = {
    1: 0.78, 2: 0.70, 3: 0.82, 4: 0.88, 5: 0.92, 6: 0.85,
    7: 0.80, 8: 0.95, 9: 1.15, 10: 1.45, 11: 1.90, 12: 1.60,
}

# Day-of-week multiplier (Mon=0). Consumer DTC peaks Sun-Mon.
DOW_SEASONALITY = {0: 1.12, 1: 1.05, 2: 1.00, 3: 0.98, 4: 0.92, 5: 0.85, 6: 1.08}

# Black Friday / Cyber Monday: 4-day window with heavy spike and deep discounts.
BFCM_SPIKE = 6.5
BFCM_DISCOUNT_RATE = 0.35
BFCM_DATES = {
    2023: (dt.date(2023, 11, 24), dt.date(2023, 11, 27)),
    2024: (dt.date(2024, 11, 29), dt.date(2024, 12, 2)),
    2025: (dt.date(2025, 11, 28), dt.date(2025, 12, 1)),
}

# --------------------------------------------------------------------------
# Product catalog
# --------------------------------------------------------------------------
N_SKUS = 180

# category -> (share_of_skus, price_min, price_max, cost_ratio, weight_min,
#              weight_max, baseline_return_rate)
CATEGORIES = {
    "Outerwear":   (0.16, 110.0, 395.0, 0.35, 2.2, 4.5, 0.22),
    "Tops":        (0.24,  38.0,  95.0, 0.29, 0.5, 1.0, 0.16),
    "Bottoms":     (0.18,  58.0, 145.0, 0.32, 0.9, 1.6, 0.24),
    "Footwear":    (0.12,  95.0, 225.0, 0.39, 2.0, 3.5, 0.26),
    "Accessories": (0.20,  18.0,  65.0, 0.25, 0.2, 0.8, 0.05),
    "Bags":        (0.10,  65.0, 185.0, 0.35, 1.2, 3.0, 0.07),
}

# Popularity follows a power law: a handful of hero SKUs carry the catalog.
SKU_POPULARITY_ALPHA = 1.15

# SCD Type 2: unit costs step up twice over the history (tariffs, new supplier).
COST_CHANGE_DATES = [dt.date(2024, 3, 1), dt.date(2025, 2, 1)]
COST_CHANGE_RANGE = (0.04, 0.07)  # +4% to +7% per event

# --------------------------------------------------------------------------
# Acquisition channels
# channel -> (share_of_new_customers, base_cac, repeat_propensity,
#             discount_affinity, return_uplift)
#
# repeat_propensity feeds a negative-binomial for lifetime order count.
# This is the lever behind Finding 4 (Google LTV >> TikTok LTV).
# --------------------------------------------------------------------------
ACQUISITION_CHANNELS = {
    "Google Search": (0.22, 44.0, 0.54, 0.06, 1.00),
    "Meta Prospecting": (0.28, 37.0, 0.31, 0.12, 1.05),
    "Meta Retargeting": (0.10, 18.0, 0.40, 0.10, 1.00),
    "TikTok Ads": (0.16, 42.0, 0.08, 0.22, 1.32),
    "Affiliate": (0.13, 0.0, 0.18, 0.88, 1.32),  # CAC is commission-based
    "Email/Organic": (0.11, 0.0, 0.44, 0.08, 0.95),
}

# Affiliate economics: commission as % of attributed revenue, plus network fee.
AFFILIATE_COMMISSION_RATE = 0.11
AFFILIATE_NETWORK_FEE_RATE = 0.03
AFFILIATE_DISCOUNT_RATE = 0.25  # the "AFF25" code
# Affiliate networks report last click, absorbing credit for organic demand.
AFFILIATE_ATTRIBUTION_INFLATION = 1.18

# Platforms over-report revenue. The size of the lie is channel-specific:
# search sits closest to truth, view-through-heavy social is the worst offender.
PLATFORM_ATTRIBUTION_INFLATION = (1.20, 1.45)  # fallback
CHANNEL_ATTRIBUTION_INFLATION = {
    "Google Search": (1.08, 1.22),
    "Meta Prospecting": (1.25, 1.45),
    "Meta Retargeting": (1.55, 1.95),
    "TikTok Ads": (1.60, 2.00),
}

# Ad costs inflate year over year (auction pressure / creative fatigue).
CAC_ANNUAL_INFLATION = 0.18

PAID_ACQUISITION_CHANNELS = ["Google Search", "Meta Prospecting",
                             "TikTok Ads", "Affiliate"]

# --------------------------------------------------------------------------
# Order economics
# --------------------------------------------------------------------------
LINES_PER_ORDER_WEIGHTS = {1: 0.52, 2: 0.27, 3: 0.14, 4: 0.07}

# End-of-season clearance. Apparel brands mark down twice a year to clear
# seasonal inventory. These windows are the second source of deep discounting
# and, like BFCM, they ship free regardless of destination.
CLEARANCE_DISCOUNT_RATE = 0.40
CLEARANCE_PARTICIPATION = 0.55   # share of orders in the window taking markdown
CLEARANCE_WINDOWS = [
    (dt.date(2023, 1, 20), dt.date(2023, 2, 5)),
    (dt.date(2023, 7, 22), dt.date(2023, 8, 6)),
    (dt.date(2024, 1, 19), dt.date(2024, 2, 4)),
    (dt.date(2024, 7, 20), dt.date(2024, 8, 4)),
    (dt.date(2025, 1, 24), dt.date(2025, 2, 9)),
    (dt.date(2025, 7, 25), dt.date(2025, 8, 10)),
]

# Non-BFCM discounting
BASE_DISCOUNT_PROBABILITY = 0.34
BASE_DISCOUNT_RATES = [0.10, 0.15, 0.20, 0.25]
BASE_DISCOUNT_WEIGHTS = [0.42, 0.30, 0.20, 0.08]

# Fulfillment cost structure
PAYMENT_FEE_RATE = 0.029          # Shopify Payments / Stripe standard
PAYMENT_FEE_FIXED = 0.30
PICK_PACK_PER_ORDER = 2.50
PICK_PACK_PER_UNIT = 0.75
PACKAGING_PER_ORDER = 1.10
RESTOCK_LABOR_PER_RETURN = 3.00

# Outbound shipping from Columbus, OH.
# Carriers bill on BILLABLE weight = max(actual, dimensional). Bulky low-density
# items (a boxed parka, a duffel) are billed well above what they weigh, which
# is why category mix -- not just order value -- drives shipping economics.
DIM_WEIGHT_FACTOR = {
    "Outerwear": 1.75, "Bags": 1.55, "Footwear": 1.40,
    "Bottoms": 1.10, "Tops": 1.00, "Accessories": 1.00,
}
SHIP_BASE_INTERCEPT = 3.60
SHIP_BASE_PER_ZONE = 1.15
SHIP_RATE_INTERCEPT = 0.32
SHIP_RATE_PER_ZONE = 0.20

# Return shipping: prepaid label, flat by zone band
RETURN_SHIP_BASE = 6.50
RETURN_SHIP_PER_ZONE = 1.05

# Free shipping policy -- deliberately mis-calibrated (Finding 2)
FREE_SHIPPING_THRESHOLD = 50.00
FLAT_SHIPPING_FEE = 7.95

# --------------------------------------------------------------------------
# Returns
# --------------------------------------------------------------------------
# Delay from order date to return request: log-normal, median ~12 days
RETURN_DELAY_LOGNORM_MU = 2.55
RETURN_DELAY_LOGNORM_SIGMA = 0.62
RETURN_WINDOW_DAYS = 60

# How strongly discount depth raises return probability.
# Deep discounts attract bracket-buyers and impulse purchases.
DISCOUNT_RETURN_COEFFICIENT = 0.95

# Probability a returned unit goes back to sellable stock, by category family
RESTOCK_RATE_APPAREL = 0.80
RESTOCK_RATE_HARDGOODS = 0.92
LIQUIDATION_RECOVERY = 0.25  # cents on the dollar for non-restockable units

RETURN_REASONS_APPAREL = {
    "size_too_small": 0.31, "size_too_large": 0.27, "changed_mind": 0.16,
    "quality": 0.13, "not_as_described": 0.08, "damaged_in_transit": 0.05,
}
RETURN_REASONS_HARDGOODS = {
    "changed_mind": 0.38, "not_as_described": 0.22, "quality": 0.20,
    "damaged_in_transit": 0.14, "size_too_small": 0.03, "size_too_large": 0.03,
}

# --------------------------------------------------------------------------
# PLANTED FINDINGS
# These are designed in, not discovered after the fact. validate_findings.py
# measures whether each one landed within tolerance.
# --------------------------------------------------------------------------

# Finding 1: two Outerwear SKUs from a supplier with defective sizing.
# High ROAS, positive CM1, negative CM2.
DEFECT_SKU_COUNT = 2
DEFECT_SKU_CATEGORY = "Outerwear"
DEFECT_RETURN_RATE = 0.41
DEFECT_COST_RATIO = 0.62          # thin margin amplifies the return damage
DEFECT_RESTOCK_RATE = 0.55        # returned in-season, often unsellable
DEFECT_DEMAND_MULTIPLIER = 7.0    # they are bestsellers -- that is the trap
DEFECT_SIZE_REASON_SHARE = 0.78   # returns cluster on size, not quality

# Finding 2: contribution margin collapses on deep-discount orders shipped
# to distant zones. Emergent, not hard-coded -- it falls out of the interaction
# between BFCM_DISCOUNT_RATE, the dimensional-weight shipping curve, and the
# discount-driven uplift in return probability. The point is not that these
# orders lose money outright; it is that they are shipped at roughly cost while
# the business books them as revenue growth.
FINDING2_DISCOUNT_THRESHOLD = 0.31   # BFCM-depth discounting
FINDING2_ZONES = (6, 7, 8)
FINDING2_MARGIN_COLLAPSE_RATIO = 0.15  # segment CM2/order vs blended
FINDING2_PROPOSED_DISCOUNT_CAP = 0.25
FINDING2_CONVERSION_LOSS = 0.18        # assumed churn if the cap is applied

# Finding 3: affiliate channel looks best on platform ROAS, worst on CM3.
# Encoded via AFFILIATE_* constants above.

# Finding 4: Google Search vs TikTok lifetime value gap.
# Encoded via ACQUISITION_CHANNELS repeat_propensity.

# --------------------------------------------------------------------------
# Deliberate data quality defects (injected in dirty.py)
# --------------------------------------------------------------------------
DEFECT_RATES = {
    "duplicate_orders": 0.004,
    "null_unit_cost": 0.012,
    "orphan_returns": 0.008,
    "price_typo": 0.0006,
    "inconsistent_product_name": 0.22,  # share of order lines, not SKUs
    "mixed_state_format": 0.09,
    "mixed_date_format": 0.18,
    "whitespace_email": 0.03,
}

# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
OUTPUT_DIR = "data/raw"
