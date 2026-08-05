"""
Deliberate data corruption.

Clean synthetic data is the single clearest signal of a portfolio project. This
module makes the raw layer look like a real export: inconsistent casing, three
date formats in one column, orphaned foreign keys, duplicated orders from a
checkout retry, and a decimal-point typo in the price feed.

Every defect here has a matching entry in docs/data_quality_report.md and a
matching test in the staging layer. Corruption without a documented fix is just
a broken dataset.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C

_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y"]


def _mixed_dates(s: pd.Series, rng: np.random.Generator, rate: float) -> pd.Series:
    d = pd.to_datetime(s)
    out = d.dt.strftime("%Y-%m-%d")
    hit = rng.random(len(s)) < rate
    alt = rng.choice([1, 2], size=len(s))
    for code in (1, 2):
        m = hit & (alt == code)
        if m.any():
            out.loc[m] = d[m].dt.strftime(_DATE_FORMATS[code])
    return out


def _mangle_name(name: str, mode: int) -> str:
    if mode == 0:
        return name.lower()
    if mode == 1:
        return name.upper()
    if mode == 2:
        return f"  {name} "
    return name.replace("Jacket", "Jkt").replace("Insulated", "Insul.")


def corrupt(orders: pd.DataFrame, lines: pd.DataFrame, rets: pd.DataFrame,
            products: pd.DataFrame, cust: pd.DataFrame,
            rng: np.random.Generator) -> dict[str, pd.DataFrame]:
    orders, lines = orders.copy(), lines.copy()
    rets, products, cust = rets.copy(), products.copy(), cust.copy()
    log = []

    # 1. Inconsistent product names on the order line (free-text snapshot)
    n = len(lines)
    hit = rng.random(n) < C.DEFECT_RATES["inconsistent_product_name"]
    modes = rng.integers(0, 4, n)
    lines.loc[hit, "product_name"] = [
        _mangle_name(nm, m) for nm, m in zip(lines.loc[hit, "product_name"], modes[hit])]
    log.append(("inconsistent_product_name", "raw_order_lines", int(hit.sum())))

    # 2. Three date formats in one text column
    orders["order_date"] = _mixed_dates(orders["order_date"], rng, C.DEFECT_RATES["mixed_date_format"])
    lines["order_date"] = _mixed_dates(lines["order_date"], rng, C.DEFECT_RATES["mixed_date_format"])
    if len(rets):
        rets["return_date"] = _mixed_dates(rets["return_date"], rng, C.DEFECT_RATES["mixed_date_format"])
        rets["original_order_date"] = _mixed_dates(rets["original_order_date"], rng, 0.0)
    log.append(("mixed_date_format", "raw_orders / raw_order_lines / raw_returns",
                int(round(C.DEFECT_RATES["mixed_date_format"] * (len(orders) + n)))))

    # 3. State code written three different ways
    hit = rng.random(len(orders)) < C.DEFECT_RATES["mixed_state_format"]
    name_map = {"CA": "California", "TX": "Texas", "NY": "New York", "FL": "Florida",
                "OH": "Ohio", "WA": "Washington", "CO": "Colorado", "IL": "Illinois"}
    variant = rng.integers(0, 2, len(orders))
    for code, full in name_map.items():
        m = hit & (orders["state_code"] == code)
        orders.loc[m & (variant == 0), "state_code"] = full
        orders.loc[m & (variant == 1), "state_code"] = code.lower() + "."
    log.append(("mixed_state_format", "raw_orders", int(hit.sum())))

    # 4. Duplicate orders (checkout retry submitted twice)
    k = int(len(orders) * C.DEFECT_RATES["duplicate_orders"])
    dup = orders.sample(k, random_state=int(rng.integers(1e6))).copy()
    dup["order_id"] = dup["order_id"] + "-R2"
    orders = pd.concat([orders, dup], ignore_index=True)
    dup_lines = lines[lines["order_id"].isin(dup["order_id"].str.replace("-R2", "", regex=False))].copy()
    dup_lines["order_id"] = dup_lines["order_id"] + "-R2"
    dup_lines["order_line_key"] = dup_lines["order_id"] + "-" + dup_lines["line_number"].astype(str)
    lines = pd.concat([lines, dup_lines], ignore_index=True)
    log.append(("duplicate_orders", "raw_orders / raw_order_lines", k))

    # 5. Missing unit cost for recently onboarded SKUs
    hit = rng.random(len(products)) < C.DEFECT_RATES["null_unit_cost"]
    products.loc[hit, "unit_cost"] = np.nan
    log.append(("null_unit_cost", "raw_products", int(hit.sum())))

    # 6. Orphaned returns -- no matching order line
    if len(rets):
        hit = rng.random(len(rets)) < C.DEFECT_RATES["orphan_returns"]
        rets.loc[hit, "order_line_key"] = None
        rets.loc[hit, "order_id"] = None
        log.append(("orphan_returns", "raw_returns", int(hit.sum())))

    # 7. Decimal-point typo in the price feed
    hit = rng.random(len(lines)) < C.DEFECT_RATES["price_typo"]
    lines.loc[hit, "unit_price_gross"] = lines.loc[hit, "unit_price_gross"] * 10
    lines.loc[hit, "line_gross_revenue"] = lines.loc[hit, "line_gross_revenue"] * 10
    log.append(("price_typo", "raw_order_lines", int(hit.sum())))

    # 8. Untrimmed / mixed-case emails
    hit = rng.random(len(cust)) < C.DEFECT_RATES["whitespace_email"]
    cust.loc[hit, "email"] = "  " + cust.loc[hit, "email"].str.upper() + " "
    log.append(("whitespace_email", "raw_customers", int(hit.sum())))

    quality_log = pd.DataFrame(log, columns=["defect", "table", "rows_affected"])
    return {"orders": orders, "lines": lines, "returns": rets,
            "products": products, "customers": cust, "quality_log": quality_log}
