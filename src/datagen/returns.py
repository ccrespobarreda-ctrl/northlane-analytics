"""
Return generation.

Three behaviours are modeled explicitly because each one changes the P&L:

  * WHEN a return happens -- log-normal delay, median ~12 days, 60-day window.
    This is why returns must be attributed to the *original order month* for
    margin analysis: a December cohort's returns land in January.

  * WHETHER the unit is resellable -- apparel returned mid-season is often
    liquidated at ~25 cents on the dollar. COGS is not fully recovered.

  * WHY it came back -- size-driven returns concentrate on specific SKUs.
    That concentration is Finding 1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .catalog import return_shipping_cost

_APPAREL = {"Outerwear", "Tops", "Bottoms", "Footwear"}


def build_returns(rng: np.random.Generator, lines: pd.DataFrame,
                  products: pd.DataFrame) -> pd.DataFrame:
    n = len(lines)

    defect_skus = set(products.loc[products["is_defect_sku"], "sku"])
    is_defect = lines["sku"].isin(defect_skus).to_numpy()

    # Heavier discounting correlates with looser purchase intent -> more returns
    disc_share = np.where(
        lines["line_gross_revenue"].to_numpy() > 0,
        lines["line_discount"].to_numpy() / lines["line_gross_revenue"].to_numpy(), 0.0)
    discount_factor = 1.0 + C.DISCOUNT_RETURN_COEFFICIENT * disc_share

    p_return = np.clip(
        lines["baseline_return_rate"].to_numpy()
        * lines["return_uplift"].to_numpy()
        * discount_factor, 0.0, 0.85)

    qty = lines["quantity"].to_numpy()
    returned_units = rng.binomial(qty, p_return)
    mask = returned_units > 0
    if not mask.any():
        return pd.DataFrame()

    src = lines.loc[mask].reset_index(drop=True)
    ru = returned_units[mask]
    m_defect = is_defect[mask]
    k = len(src)

    # ---- Timing ----------------------------------------------------------
    delay = rng.lognormal(C.RETURN_DELAY_LOGNORM_MU, C.RETURN_DELAY_LOGNORM_SIGMA, k)
    delay = np.clip(np.round(delay), 2, C.RETURN_WINDOW_DAYS)
    return_date = pd.DatetimeIndex(src["order_date"]) + pd.to_timedelta(delay, unit="D")

    # Returns after the observation window are simply not yet visible.
    visible = return_date <= pd.Timestamp(C.END_DATE)
    src, ru, m_defect = src[visible].reset_index(drop=True), ru[visible], m_defect[visible]
    return_date = return_date[visible]
    k = len(src)

    # ---- Disposition -----------------------------------------------------
    is_apparel = src["category"].isin(_APPAREL).to_numpy()
    restock_p = np.where(is_apparel, C.RESTOCK_RATE_APPAREL, C.RESTOCK_RATE_HARDGOODS)
    restock_p = np.where(m_defect, C.DEFECT_RESTOCK_RATE, restock_p)
    restocked = rng.random(k) < restock_p

    unit_cost = src["unit_cost"].to_numpy()
    cogs_at_risk = unit_cost * ru
    cogs_recovered = np.where(restocked, cogs_at_risk, cogs_at_risk * C.LIQUIDATION_RECOVERY)

    disposition = np.where(restocked, "restock",
                           np.where(rng.random(k) < 0.8, "liquidate", "destroy"))

    # ---- Refund ----------------------------------------------------------
    unit_net = src["line_net_revenue"].to_numpy() / src["quantity"].to_numpy()
    refund = np.round(unit_net * ru, 2)

    # ---- Reason ----------------------------------------------------------
    ap_r, ap_p = zip(*C.RETURN_REASONS_APPAREL.items())
    hg_r, hg_p = zip(*C.RETURN_REASONS_HARDGOODS.items())
    reason = np.where(
        is_apparel,
        rng.choice(ap_r, size=k, p=np.array(ap_p) / sum(ap_p)),
        rng.choice(hg_r, size=k, p=np.array(hg_p) / sum(hg_p)))

    # Defective SKUs: returns collapse onto sizing, which is the diagnostic clue
    size_reasons = rng.choice(["size_too_small", "size_too_large"], size=k, p=[0.55, 0.45])
    force_size = m_defect & (rng.random(k) < C.DEFECT_SIZE_REASON_SHARE)
    reason = np.where(force_size, size_reasons, reason)

    return pd.DataFrame({
        "return_id": [f"R{500000 + i}" for i in range(k)],
        "order_line_key": src["order_line_key"],
        "order_id": src["order_id"],
        "sku": src["sku"],
        "original_order_date": src["order_date"],
        "return_date": return_date,
        "quantity_returned": ru,
        "refund_amount": refund,
        "return_reason": reason,
        "return_shipping_cost": return_shipping_cost(src["shipping_zone"].to_numpy()),
        "restock_labor_cost": np.round(C.RESTOCK_LABOR_PER_RETURN, 2),
        "restocked": restocked,
        "disposition": disposition,
        "cogs_recovered": np.round(cogs_recovered, 2),
    })
