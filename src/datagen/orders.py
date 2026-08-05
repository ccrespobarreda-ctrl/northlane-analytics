"""
Order and order-line generation, plus the full landed-cost model.

Order-level costs (shipping, payment fees, pick/pack) are allocated down to the
line so that contribution margin can be computed at SKU grain:

  * shipping   -> allocated by weight share      (heavy items cause the cost)
  * payment    -> allocated by value share       (the fee is a % of value)
  * pick/pack  -> allocated by unit share        (labor scales with units)

Any allocation is a modeling choice, not a fact. The bases above are stated in
docs/business_rules.md so a reader can disagree with them explicitly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .catalog import outbound_shipping_cost

# Approximate STATE-level base sales tax rates (%), illustrative only.
# Local add-ons and apparel exemptions (e.g. PA, NJ, MN) are not modeled.
# Tax is carried on the order so that downstream models must exclude it
# from revenue -- which is the point of including it at all.
_STATE_TAX_RATE = {
    "AL": 4.00, "AK": 0.00, "AZ": 5.60, "AR": 6.50, "CA": 7.25, "CO": 2.90,
    "CT": 6.35, "DE": 0.00, "DC": 6.00, "FL": 6.00, "GA": 4.00, "HI": 4.00,
    "ID": 6.00, "IL": 6.25, "IN": 7.00, "IA": 6.00, "KS": 6.50, "KY": 6.00,
    "LA": 4.45, "ME": 5.50, "MD": 6.00, "MA": 6.25, "MI": 6.00, "MN": 6.875,
    "MS": 7.00, "MO": 4.225, "MT": 0.00, "NE": 5.50, "NV": 6.85, "NH": 0.00,
    "NJ": 6.625, "NM": 4.875, "NY": 4.00, "NC": 4.75, "ND": 5.00, "OH": 5.75,
    "OK": 4.50, "OR": 0.00, "PA": 6.00, "RI": 7.00, "SC": 6.00, "SD": 4.20,
    "TN": 7.00, "TX": 6.25, "UT": 6.10, "VT": 6.00, "VA": 5.30, "WA": 6.50,
    "WV": 6.00, "WI": 5.00, "WY": 4.00,
}


def _in_windows(dates: pd.Series, windows) -> np.ndarray:
    flag = np.zeros(len(dates), dtype=bool)
    d = pd.DatetimeIndex(dates)
    for start, end in windows:
        flag |= (d >= pd.Timestamp(start)) & (d <= pd.Timestamp(end))
    return flag


def _in_bfcm(dates: pd.Series) -> np.ndarray:
    return _in_windows(dates, C.BFCM_DATES.values())


def build_order_lines(rng: np.random.Generator, cal: pd.DataFrame,
                      cust: pd.DataFrame, products: pd.DataFrame,
                      geo: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    n_orders = len(cal)

    orders = cal.copy().reset_index(drop=True)
    orders["order_id"] = [f"NL{100000 + i}" for i in range(n_orders)]

    attrs = cust.set_index("customer_key")
    orders["state_code"] = attrs["state_code"].reindex(orders["customer_key"]).to_numpy()
    orders["acquisition_channel"] = attrs["acquisition_channel"].reindex(orders["customer_key"]).to_numpy()
    orders["discount_affinity"] = attrs["discount_affinity"].reindex(orders["customer_key"]).to_numpy()
    orders["return_uplift"] = attrs["return_uplift"].reindex(orders["customer_key"]).to_numpy()

    zone_map = geo.set_index("state_code")["shipping_zone"]
    orders["shipping_zone"] = orders["state_code"].map(zone_map).to_numpy()

    # Sales channel: most volume is D2C; Amazon and wholesale are separate.
    orders["sales_channel"] = rng.choice(
        ["Shopify D2C", "Amazon FBA", "Wholesale"], size=n_orders, p=[0.82, 0.155, 0.025])

    # ---- Lines per order -------------------------------------------------
    ks = np.array(list(C.LINES_PER_ORDER_WEIGHTS))
    ps = np.array(list(C.LINES_PER_ORDER_WEIGHTS.values()))
    n_lines = rng.choice(ks, size=n_orders, p=ps / ps.sum())

    order_idx = np.repeat(np.arange(n_orders), n_lines)
    line_number = np.concatenate([np.arange(1, k + 1) for k in n_lines])
    n_rows = len(order_idx)

    # ---- SKU selection ---------------------------------------------------
    current = products[products["is_current"]].reset_index(drop=True)
    w = current["demand_weight"].to_numpy()
    sku_pos = rng.choice(len(current), size=n_rows, p=w / w.sum())
    sku = current["sku"].to_numpy()[sku_pos]

    line_dates = pd.DatetimeIndex(orders["order_date"].to_numpy()[order_idx])

    # ---- SCD2 cost version valid on the order date -----------------------
    version = np.ones(n_rows, dtype=int)
    for change in C.COST_CHANGE_DATES:
        version += (line_dates >= pd.Timestamp(change)).astype(int)
    product_key = np.char.add(np.char.add(sku.astype(str), "-V"), version.astype(str))

    pmap = products.set_index("product_key")
    unit_cost = pmap["unit_cost"].reindex(product_key).to_numpy()
    list_price = pmap["list_price"].reindex(product_key).to_numpy()
    weight = pmap["weight_lbs"].reindex(product_key).to_numpy()
    category = pmap["category"].reindex(product_key).to_numpy()
    base_return = pmap["baseline_return_rate"].reindex(product_key).to_numpy()

    quantity = np.where(rng.random(n_rows) < 0.14, 2, 1)

    # ---- Discounting -----------------------------------------------------
    is_bfcm = _in_bfcm(pd.Series(line_dates))
    affinity = orders["discount_affinity"].to_numpy()[order_idx]
    is_affiliate = orders["acquisition_channel"].to_numpy()[order_idx] == "Affiliate"

    disc_rate = np.zeros(n_rows)
    codes = np.full(n_rows, None, dtype=object)

    # 1. Affiliate customers overwhelmingly redeem the AFF25 code
    aff_hit = is_affiliate & (rng.random(n_rows) < affinity)
    disc_rate[aff_hit] = C.AFFILIATE_DISCOUNT_RATE
    codes[aff_hit] = "AFF25"

    # 2. Ordinary promo usage
    promo_hit = (~aff_hit) & (rng.random(n_rows) < C.BASE_DISCOUNT_PROBABILITY * (1 + affinity))
    r = rng.choice(C.BASE_DISCOUNT_RATES, size=n_rows,
                   p=np.array(C.BASE_DISCOUNT_WEIGHTS) / sum(C.BASE_DISCOUNT_WEIGHTS))
    disc_rate[promo_hit] = r[promo_hit]
    codes[promo_hit] = np.char.add("SAVE", (r[promo_hit] * 100).astype(int).astype(str))

    # 3. End-of-season clearance
    in_clear = _in_windows(pd.Series(line_dates), C.CLEARANCE_WINDOWS)
    clear_hit = in_clear & (rng.random(n_rows) < C.CLEARANCE_PARTICIPATION)
    disc_rate[clear_hit] = C.CLEARANCE_DISCOUNT_RATE
    codes[clear_hit] = "SEASONEND40"

    # 4. BFCM overrides everything
    disc_rate[is_bfcm] = C.BFCM_DISCOUNT_RATE
    codes[is_bfcm] = "BFCM"

    gross = np.round(list_price * quantity, 2)
    discount = np.round(gross * disc_rate, 2)
    net = np.round(gross - discount, 2)

    lines = pd.DataFrame({
        "order_id": orders["order_id"].to_numpy()[order_idx],
        "line_number": line_number,
        "order_date": line_dates,
        "customer_key": orders["customer_key"].to_numpy()[order_idx],
        "sku": sku,
        "product_key": product_key,
        "product_name": pmap["product_name"].reindex(product_key).to_numpy(),
        "category": category,
        "quantity": quantity,
        "unit_price_gross": list_price,
        "unit_cost": unit_cost,
        "weight_lbs": weight,
        "line_gross_revenue": gross,
        "line_discount": discount,
        "line_net_revenue": net,
        "line_cogs": np.round(unit_cost * quantity, 2),
        "discount_code": codes,
        "baseline_return_rate": base_return,
        "return_uplift": orders["return_uplift"].to_numpy()[order_idx],
        "shipping_zone": orders["shipping_zone"].to_numpy()[order_idx],
        "sales_channel": orders["sales_channel"].to_numpy()[order_idx],
        "_order_idx": order_idx,
    })
    # Billable weight drives the carrier invoice, not scale weight.
    lines["dim_factor"] = lines["category"].map(C.DIM_WEIGHT_FACTOR).fillna(1.0)
    lines["billable_weight_lbs"] = np.round(
        lines["weight_lbs"] * lines["dim_factor"], 2)
    lines["line_weight"] = lines["billable_weight_lbs"] * lines["quantity"]

    # ---- Order-level rollup ---------------------------------------------
    agg = lines.groupby("_order_idx").agg(
        order_net_revenue=("line_net_revenue", "sum"),
        order_gross_revenue=("line_gross_revenue", "sum"),
        order_weight=("line_weight", "sum"),
        order_units=("quantity", "sum"),
    ).reindex(np.arange(n_orders)).fillna(0.0)

    orders = pd.concat([orders, agg.reset_index(drop=True)], axis=1)

    # Free shipping above the threshold -- the mis-calibrated policy
    orders["shipping_revenue"] = np.where(
        orders["order_net_revenue"] >= C.FREE_SHIPPING_THRESHOLD, 0.0, C.FLAT_SHIPPING_FEE)

    orders["shipping_cost"] = outbound_shipping_cost(
        orders["shipping_zone"].to_numpy(), orders["order_weight"].to_numpy())

    tax_rate = orders["state_code"].map(_STATE_TAX_RATE).fillna(0.0) / 100.0
    orders["sales_tax"] = np.round(orders["order_net_revenue"] * tax_rate, 2)

    charged = orders["order_net_revenue"] + orders["shipping_revenue"] + orders["sales_tax"]
    orders["payment_fee"] = np.round(charged * C.PAYMENT_FEE_RATE + C.PAYMENT_FEE_FIXED, 2)

    orders["pick_pack_cost"] = np.round(
        C.PICK_PACK_PER_ORDER + C.PICK_PACK_PER_UNIT * orders["order_units"]
        + C.PACKAGING_PER_ORDER, 2)

    # ---- Allocate order costs down to lines ------------------------------
    o = orders.set_index(orders.index)
    w_share = lines["line_weight"] / lines["_order_idx"].map(o["order_weight"]).replace(0, np.nan)
    v_share = lines["line_net_revenue"] / lines["_order_idx"].map(o["order_net_revenue"]).replace(0, np.nan)
    u_share = lines["quantity"] / lines["_order_idx"].map(o["order_units"]).replace(0, np.nan)

    lines["shipping_revenue_alloc"] = np.round(lines["_order_idx"].map(o["shipping_revenue"]) * v_share.fillna(0), 2)
    lines["shipping_cost_alloc"] = np.round(lines["_order_idx"].map(o["shipping_cost"]) * w_share.fillna(0), 2)
    lines["payment_fee_alloc"] = np.round(lines["_order_idx"].map(o["payment_fee"]) * v_share.fillna(0), 2)
    lines["pick_pack_alloc"] = np.round(lines["_order_idx"].map(o["pick_pack_cost"]) * u_share.fillna(0), 2)

    lines["order_line_key"] = lines["order_id"] + "-" + lines["line_number"].astype(str)
    lines = lines.drop(columns=["_order_idx", "line_weight", "dim_factor"])

    orders = orders.drop(columns=["discount_affinity", "return_uplift"])
    return orders, lines
