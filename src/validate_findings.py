#!/usr/bin/env python3
"""
Generator self-test.

Asserts that the four planted findings landed at the intended magnitude, and
that the business as a whole has believable unit economics. If a calibration
change quietly kills a finding, this catches it before the dashboard is built.

    python src/validate_findings.py

Reads data/reference/*.parquet (pre-corruption frames written by
generate_data.py --emit-reference). This is a build-time check, NOT the
analysis: the dashboard is built from data/raw through the SQL layer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from datagen import config as C

REF = Path("data/reference")
OK, FAIL = "PASS", "FAIL"
_results: list[tuple[str, str, str]] = []


def check(name: str, passed: bool, detail: str) -> None:
    _results.append((name, OK if passed else FAIL, detail))


# --------------------------------------------------------------------------
# Load and build the contribution-margin spine
# --------------------------------------------------------------------------
def load() -> dict[str, pd.DataFrame]:
    return {p.stem: pd.read_parquet(p) for p in REF.glob("*.parquet")}


def line_margins(f: dict[str, pd.DataFrame]) -> pd.DataFrame:
    L, R = f["lines"], f["returns"]
    ret = R.groupby("order_line_key").agg(
        refund=("refund_amount", "sum"), cogs_rec=("cogs_recovered", "sum"),
        ret_ship=("return_shipping_cost", "sum"), lab=("restock_labor_cost", "sum"),
        units_ret=("quantity_returned", "sum")).reset_index()
    X = L.merge(ret, on="order_line_key", how="left")
    X[["refund", "cogs_rec", "ret_ship", "lab", "units_ret"]] = \
        X[["refund", "cogs_rec", "ret_ship", "lab", "units_ret"]].fillna(0.0)
    X["cm1"] = X.line_net_revenue - X.refund - X.line_cogs + X.cogs_rec
    X["cm2"] = (X.cm1 + X.shipping_revenue_alloc - X.shipping_cost_alloc
                - X.payment_fee_alloc - X.pick_pack_alloc - X.ret_ship - X.lab)
    X["year"] = pd.to_datetime(X.order_date).dt.year
    X["discount_rate"] = np.where(X.line_gross_revenue > 0,
                                  X.line_discount / X.line_gross_revenue, 0.0)
    return X


def order_margins(f: dict[str, pd.DataFrame]) -> pd.DataFrame:
    O, L, R = f["orders"], f["lines"], f["returns"]
    cogs = L.groupby("order_id")["line_cogs"].sum().rename("cogs").reset_index()
    disc = L.groupby("order_id")[["line_gross_revenue", "line_discount"]].sum().reset_index()
    ret = R.groupby("order_id").agg(
        refund=("refund_amount", "sum"), cogs_rec=("cogs_recovered", "sum"),
        ret_ship=("return_shipping_cost", "sum"), lab=("restock_labor_cost", "sum")).reset_index()
    Y = O.merge(cogs, on="order_id", how="left").merge(disc, on="order_id", how="left") \
         .merge(ret, on="order_id", how="left").fillna(0.0)
    Y["cm1"] = Y.order_net_revenue - Y.refund - Y.cogs + Y.cogs_rec
    Y["cm2"] = (Y.cm1 + Y.shipping_revenue - Y.shipping_cost - Y.payment_fee
                - Y.pick_pack_cost - Y.ret_ship - Y.lab)
    Y["year"] = pd.to_datetime(Y.order_date).dt.year
    Y["discount_rate"] = np.where(Y.line_gross_revenue > 0,
                                  Y.line_discount / Y.line_gross_revenue, 0.0)
    return Y


# --------------------------------------------------------------------------
# Health of the business as a whole
# --------------------------------------------------------------------------
def business_health(Y: pd.DataFrame, X: pd.DataFrame, ads: pd.DataFrame) -> None:
    print("\n" + "=" * 78)
    print("BUSINESS SCALE AND MARGIN STRUCTURE")
    print("=" * 78)
    ads["year"] = pd.to_datetime(ads.date).dt.year
    t = Y.groupby("year").agg(orders=("order_id", "count"),
                              gross=("order_gross_revenue", "sum"),
                              net=("order_net_revenue", "sum"),
                              cm1=("cm1", "sum"), cm2=("cm2", "sum"))
    t["spend"] = ads.groupby("year")["spend"].sum()
    t["cm3"] = t.cm2 - t.spend
    # Margin denominators use NET revenue -- after discounts and returns --
    # matching DTC convention. AOV uses discounted revenue, because an order is
    # worth what the customer paid at checkout.
    t["refunds"] = Y.groupby("year")["refund"].sum()
    t["net_after_returns"] = t.net - t.refunds
    t["aov"] = t.net / t.orders
    t["cm1_pct"] = t.cm1 / t.net_after_returns
    t["cm2_pct"] = t.cm2 / t.net_after_returns
    t["cm3_pct"] = t.cm3 / t.net_after_returns
    t["mer"] = t.net_after_returns / t.spend
    print(t[["orders", "gross", "net", "aov", "cm1_pct", "cm2_pct",
             "cm3_pct", "mer"]].round(3).to_string())

    y25 = t.loc[2025]
    check("Revenue scale (2025 gross $8-11M)", 8e6 <= y25.gross <= 11e6,
          f"${y25.gross:,.0f}")
    check("AOV realistic ($120-210)", 120 <= y25.aov <= 210, f"${y25.aov:.2f}")
    check("CM1 margin 50-62%", 0.50 <= y25.cm1_pct <= 0.62, f"{y25.cm1_pct:.1%}")
    check("CM2 margin 28-40%", 0.28 <= y25.cm2_pct <= 0.40, f"{y25.cm2_pct:.1%}")
    check("CM3 positive but thin (5-16%)", 0.05 < y25.cm3_pct <= 0.16, f"{y25.cm3_pct:.1%}")
    check("Blended MER 3.0-5.5", 3.0 <= y25.mer <= 5.5, f"{y25.mer:.2f}")

    rr = X.units_ret.sum() / X.quantity.sum()
    check("Unit return rate 15-22%", 0.15 <= rr <= 0.22, f"{rr:.1%}")


# --------------------------------------------------------------------------
# Finding 1 -- defective Outerwear SKUs
# --------------------------------------------------------------------------
def finding_1(X: pd.DataFrame, products: pd.DataFrame) -> None:
    print("\n" + "=" * 78)
    print("FINDING 1  Two Outerwear SKUs: positive CM1, negative CM2")
    print("=" * 78)
    defect = set(products.loc[products.is_defect_sku, "sku"])
    X = X.assign(grp=np.where(X.sku.isin(defect), "defect SKUs", "rest of catalog"))
    g = X.groupby("grp").agg(units=("quantity", "sum"), ret=("units_ret", "sum"),
                             net=("line_net_revenue", "sum"),
                             cm1=("cm1", "sum"), cm2=("cm2", "sum"))
    g["return_rate"] = g.ret / g.units
    g["cm1_pct"] = g.cm1 / g.net
    g["cm2_pct"] = g.cm2 / g.net
    g["cm2_per_unit"] = g.cm2 / g.units
    print(g[["units", "return_rate", "net", "cm1_pct", "cm2_pct", "cm2_per_unit"]]
          .round(3).to_string())

    d = g.loc["defect SKUs"]
    base = g.loc["rest of catalog"]
    check("F1: return rate >= 2x catalog", d.return_rate >= 2 * base.return_rate,
          f"{d.return_rate:.1%} vs {base.return_rate:.1%}")
    check("F1: CM1 positive", d.cm1 > 0, f"${d.cm1:,.0f}")
    check("F1: CM2 negative", d.cm2 < 0, f"${d.cm2:,.0f}")

    # Recovery scenario: sizing fixed, return rate falls to the Outerwear baseline
    base_rr = C.CATEGORIES["Outerwear"][6]
    dx = X[X.grp == "defect SKUs"]
    ann_units = dx.quantity.sum() / 3
    loss_per_returned_unit = (
        (dx.refund.sum() - dx.cogs_rec.sum() + dx.ret_ship.sum() + dx.lab.sum())
        / max(dx.units_ret.sum(), 1))
    delta_rr = d.return_rate - base_rr
    recovery = ann_units * delta_rr * loss_per_returned_unit
    print(f"\n  Annual units: {ann_units:,.0f}   avoidable returns/yr: "
          f"{ann_units * delta_rr:,.0f}   cost per return: ${loss_per_returned_unit:,.2f}")
    print(f"  >>> Estimated annual recovery if sizing is fixed "
          f"({d.return_rate:.0%} -> {base_rr:.0%}): ${recovery:,.0f}")
    print(f"  >>> Annual CM2 bleed if delisted instead: ${-dx.cm2.sum() / 3:,.0f}")
    check("F1: recovery is material (> $40k/yr)", recovery > 40_000, f"${recovery:,.0f}")


# --------------------------------------------------------------------------
# Finding 2 -- deep discounts + distant zones
# --------------------------------------------------------------------------
def finding_2(Y: pd.DataFrame) -> None:
    print("\n" + "=" * 78)
    print("FINDING 2  Contribution collapses on deep-discount orders to far zones")
    print("=" * 78)
    Y = Y.assign(
        deep=Y.discount_rate >= C.FINDING2_DISCOUNT_THRESHOLD,
        far=Y.shipping_zone.isin(C.FINDING2_ZONES))
    piv = Y.groupby(["deep", "far"]).agg(orders=("order_id", "count"),
                                         aov=("order_net_revenue", "mean"),
                                         net=("order_net_revenue", "sum"),
                                         cm2=("cm2", "sum"))
    piv["cm2_per_order"] = piv.cm2 / piv.orders
    piv["cm2_pct"] = piv.cm2 / piv.net
    piv.index = piv.index.set_names(["deep_discount", "far_zone"])
    print(piv.round(2).to_string())

    print("\n  CM2 per order by shipping zone, deep-discount orders only:")
    z = Y[Y.deep].groupby("shipping_zone").agg(orders=("order_id", "count"),
                                               cm2_per_order=("cm2", "mean"))
    print("  " + z.round(2).to_string().replace("\n", "\n  "))

    seg = piv.loc[(True, True)]
    blended = Y.cm2.sum() / len(Y)
    ratio = seg.cm2_per_order / blended
    check("F2: margin collapse >= 6x vs blended",
          ratio <= C.FINDING2_MARGIN_COLLAPSE_RATIO,
          f"${seg.cm2_per_order:.2f} vs ${blended:.2f}/order ({ratio:.0%})")
    check("F2: segment is material (>2% of orders)",
          seg.orders / len(Y) > 0.02, f"{seg.orders / len(Y):.1%} of orders")

    # Scenario: cap the deepest discount at 25%. Gross revenue recovered on the
    # retained orders flows almost entirely to CM2 (COGS is already committed).
    deep = Y[Y.deep]
    uplift = (deep.discount_rate - C.FINDING2_PROPOSED_DISCOUNT_CAP).clip(lower=0)
    recovered = (deep.line_gross_revenue * uplift).sum()
    retained = 1 - C.FINDING2_CONVERSION_LOSS
    lost_cm2 = deep.cm2.sum() * C.FINDING2_CONVERSION_LOSS
    annual = (recovered * retained - lost_cm2) / 3
    print(f"\n  >>> Scenario: cap discounts at "
          f"{C.FINDING2_PROPOSED_DISCOUNT_CAP:.0%}, assume "
          f"{C.FINDING2_CONVERSION_LOSS:.0%} conversion loss")
    print(f"  >>> Estimated annual CM2 gain: ${annual:,.0f}")
    check("F2: discount cap recovers > $50k/yr", annual > 50_000, f"${annual:,.0f}")


# --------------------------------------------------------------------------
# Finding 3 -- affiliate looks best on ROAS, worst on CM3
# --------------------------------------------------------------------------
def finding_3(Y: pd.DataFrame, ads: pd.DataFrame) -> None:
    print("\n" + "=" * 78)
    print("FINDING 3  Affiliate: best platform ROAS, worst true contribution")
    print("=" * 78)
    spend = ads.groupby("channel").agg(spend=("spend", "sum"),
                                       rep_rev=("platform_reported_revenue", "sum"))
    ch = Y.groupby("acquisition_channel").agg(net=("order_net_revenue", "sum"),
                                              cm2=("cm2", "sum"),
                                              orders=("order_id", "count"))
    ch = ch.join(spend).fillna(0.0)
    ch["platform_roas"] = ch.rep_rev / ch.spend.replace(0, np.nan)
    ch["true_roas"] = ch.net / ch.spend.replace(0, np.nan)
    ch["cm3"] = ch.cm2 - ch.spend
    ch["cm3_pct"] = ch.cm3 / ch.net
    ch = ch.sort_values("platform_roas", ascending=False)
    print(ch[["net", "spend", "platform_roas", "true_roas", "cm2", "cm3", "cm3_pct"]]
          .round(2).to_string())

    # Owned channels and retargeting always flatter ROAS; the meaningful
    # comparison is between paid ACQUISITION channels.
    paid = ch.loc[ch.index.intersection(C.PAID_ACQUISITION_CHANNELS)]
    best_roas = paid.platform_roas.idxmax()
    check("F3: Affiliate has the highest platform ROAS", best_roas == "Affiliate",
          f"top ROAS = {best_roas} ({paid.platform_roas.max():.2f})")
    check("F3: Affiliate CM3 is negative", paid.loc["Affiliate", "cm3"] < 0,
          f"${paid.loc['Affiliate', 'cm3']:,.0f}")
    # The headline is the inversion: the channel that ranks first on the metric
    # the team optimizes ranks last but one on the metric that pays salaries.
    rank_roas = int(paid.platform_roas.rank(ascending=False).loc["Affiliate"])
    rank_cm3 = int(paid.cm3_pct.rank(ascending=False).loc["Affiliate"])
    check("F3: ROAS rank inverts vs CM3 rank", rank_roas == 1 and rank_cm3 >= 3,
          f"ROAS #{rank_roas} of {len(paid)}, CM3 #{rank_cm3} of {len(paid)}")

    aff = ch.loc["Affiliate"]
    alt = ch.loc["Meta Prospecting"]
    delta = (alt.cm3_pct - aff.cm3_pct) * aff.net / 3
    print(f"\n  >>> Annual CM3 gap vs Meta Prospecting on the same revenue: "
          f"${delta:,.0f}/yr")


# --------------------------------------------------------------------------
# Finding 4 -- LTV gap by acquisition channel
# --------------------------------------------------------------------------
def finding_4(Y: pd.DataFrame, cust: pd.DataFrame, ads: pd.DataFrame) -> None:
    print("\n" + "=" * 78)
    print("FINDING 4  12-month CM2 LTV vs CAC by acquisition channel")
    print("=" * 78)
    cutoff = pd.Timestamp(C.END_DATE) - pd.Timedelta(days=365)
    first = pd.to_datetime(cust.set_index("customer_key")["first_order_date"])
    Y = Y.assign(first=Y.customer_key.map(first))
    Y["days"] = (pd.to_datetime(Y.order_date) - Y["first"]).dt.days

    complete = cust[pd.to_datetime(cust.first_order_date) <= cutoff]
    w = Y[(Y.days <= 365) & (Y.customer_key.isin(set(complete.customer_key)))]

    t = w.groupby("acquisition_channel").agg(cm2=("cm2", "sum"),
                                             orders=("order_id", "count"),
                                             customers=("customer_key", "nunique"))
    t["orders_per_cust"] = t.orders / t.customers
    t["ltv12_cm2"] = t.cm2 / t.customers

    spend_win = ads[pd.to_datetime(ads.date) <= cutoff].groupby("channel")["spend"].sum()
    n_new = complete.groupby("acquisition_channel").size()
    t["cac"] = (spend_win / n_new).reindex(t.index).fillna(0.0)
    t["ltv_cac"] = t.ltv12_cm2 / t.cac.replace(0, np.nan)
    print(t[["customers", "orders_per_cust", "ltv12_cm2", "cac", "ltv_cac"]]
          .round(2).to_string())

    g, tk = t.loc["Google Search"], t.loc["TikTok Ads"]
    ratio = g.ltv12_cm2 / tk.ltv12_cm2
    check("F4: Google LTV >= 2.2x TikTok", ratio >= 2.2, f"{ratio:.2f}x")
    check("F4: Google LTV:CAC > 1.5", g.ltv_cac > 1.5, f"{g.ltv_cac:.2f}")
    check("F4: TikTok LTV:CAC < 1.0", tk.ltv_cac < 1.0, f"{tk.ltv_cac:.2f}")


def main() -> int:
    if not REF.exists():
        print("data/reference/ not found. Run:\n"
              "  python src/generate_data.py --emit-reference", file=sys.stderr)
        return 2

    f = load()
    X, Y = line_margins(f), order_margins(f)

    business_health(Y, X, f["ad_spend"])
    finding_1(X, f["products"])
    finding_2(Y)
    finding_3(Y, f["ad_spend"])
    finding_4(Y, f["customers"], f["ad_spend"])

    print("\n" + "=" * 78)
    print("SELF-TEST SUMMARY")
    print("=" * 78)
    for name, status, detail in _results:
        marker = " " if status == OK else ">"
        print(f"{marker} [{status}] {name:<45} {detail}")
    failed = sum(1 for _, s, _ in _results if s == FAIL)
    print(f"\n{len(_results) - failed}/{len(_results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
