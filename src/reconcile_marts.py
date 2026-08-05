#!/usr/bin/env python3
"""
End-to-end reconciliation.

The generator knows the truth. The pipeline only ever sees the corrupted export.
This script runs both and compares them, which is the only way to prove the
cleaning logic actually works rather than merely running without errors.

    python src/reconcile_marts.py

A pipeline that loads without failing but quietly drops 3% of revenue looks
identical to a correct one until someone checks. This is that check.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_findings import load, line_margins, order_margins  # noqa: E402

# Two tolerance classes, because the metrics are not equally forgiving.
#
# EXACT: row counts, revenue, refunds and ad spend must survive the cleaning
# untouched. Nothing the pipeline does to a corrupted export should move them,
# so anything beyond float rounding is a defect. A single loose tolerance here
# would have tolerated a $42k revenue overstatement -- verified by disabling the
# deduplication and watching it pass.
TOLERANCE_EXACT = 0.0001        # 0.01%
#
# IMPUTED: five SKU unit costs were destroyed in the source and are imputed from
# category medians, so every cost-derived figure carries a small, known and
# irreducible variance. The band is set just above the observed residual, not
# rounded up for comfort.
TOLERANCE_IMPUTED = 0.001       # 0.1%
_rows: list[dict] = []


def compare(metric: str, reference: float, pipeline: float,
            tolerance: float = TOLERANCE_EXACT, unit: str = "$") -> None:
    denom = abs(reference) if reference else 1.0
    variance = (pipeline - reference) / denom
    _rows.append({
        "metric": metric,
        "reference": reference,
        "pipeline": pipeline,
        "variance_pct": variance,
        "status": "PASS" if abs(variance) <= tolerance else "FAIL",
        "unit": unit,
    })


def q(conn, sql: str) -> pd.DataFrame:
    """Query without going through pandas' SQLAlchemy path -- psycopg2 alone is
    enough here and avoids pulling an ORM in for six read-only queries."""
    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("Set DATABASE_URL", file=sys.stderr)
        return 2

    ref = load()

    # The pipeline cannot see returns whose foreign key was destroyed, so the
    # reference must not either. Identifying them from the raw export -- rather
    # than quietly widening the tolerance -- is the difference between
    # reconciling and hand-waving.
    raw_returns = pd.read_csv("data/raw/raw_returns.csv", usecols=["return_id",
                                                                   "order_line_key"])
    orphaned_ids = set(raw_returns.loc[raw_returns.order_line_key.isna(), "return_id"])
    print(f"Excluding {len(orphaned_ids):,} orphaned returns from the reference "
          f"(the pipeline quarantines them; see int_returns_orphaned)")

    ref_visible = dict(ref)
    ref_visible["returns"] = ref["returns"][~ref["returns"].return_id.isin(orphaned_ids)]

    X = line_margins(ref_visible)
    Y = order_margins(ref_visible)

    # Quantify what the quarantine costs in reported margin, so the number is
    # disclosed rather than absorbed.
    X_all = line_margins(ref)
    quarantine_cm2_overstatement = X.cm2.sum() - X_all.cm2.sum()

    conn = psycopg2.connect(dsn)
    m = "analytics_marts"

    # ---- Volume ---------------------------------------------------------
    counts = q(conn, f"""
        select
            (select count(*) from {m}.fct_order_lines)          as lines,
            (select count(distinct order_id) from {m}.fct_order_lines) as orders,
            (select count(*) from {m}.dim_customer)             as customers,
            (select count(*) from {m}.dim_product)              as product_versions
    """).iloc[0]
    compare("Order lines", len(X), counts.lines, unit="rows")
    compare("Distinct orders", Y.order_id.nunique(), counts.orders, unit="rows")
    compare("Customers", ref["customers"].customer_key.nunique(),
            counts.customers, unit="rows")

    # ---- Revenue and margin, FY2025 -------------------------------------
    fy = q(conn, f"""
        select
            sum(gross_revenue)              as gross_revenue,
            sum(discounted_revenue)         as discounted_revenue,
            sum(net_revenue)                as net_revenue,
            sum(refund_amount)              as refunds,
            sum(cogs)                       as cogs,
            sum(cm1)                        as cm1,
            sum(cm2)                        as cm2
        from {m}.fct_order_lines
        where extract(year from order_date) = 2025
    """).iloc[0]
    r25 = X[X.year == 2025]
    compare("FY2025 gross revenue", r25.line_gross_revenue.sum(), float(fy.gross_revenue))
    compare("FY2025 discounted revenue", r25.line_net_revenue.sum(),
            float(fy.discounted_revenue))
    compare("FY2025 net revenue (after returns)",
            r25.line_net_revenue.sum() - r25.refund.sum(), float(fy.net_revenue))
    compare("FY2025 refunds", r25.refund.sum(), float(fy.refunds))
    compare("FY2025 COGS", r25.line_cogs.sum(), float(fy.cogs),
            tolerance=TOLERANCE_IMPUTED)
    compare("FY2025 CM1", r25.cm1.sum(), float(fy.cm1),
            tolerance=TOLERANCE_IMPUTED)
    compare("FY2025 CM2", r25.cm2.sum(), float(fy.cm2),
            tolerance=TOLERANCE_IMPUTED)

    # ---- Finding 1: the two worst SKUs by CM2 ---------------------------
    worst = q(conn, f"""
        select sku,
               sum(quantity)                                    as units,
               sum(units_returned)::numeric / sum(quantity)      as return_rate,
               sum(cm1)                                         as cm1,
               sum(cm2)                                         as cm2
        from {m}.fct_order_lines
        group by sku
        having sum(quantity) > 500
        order by sum(cm2) asc
        limit 2
    """)
    defect = set(ref["products"].loc[ref["products"].is_defect_sku, "sku"])
    found = set(worst.sku)
    print("\nFinding 1 -- two worst SKUs by CM2, discovered from the dirty data:")
    print(worst.to_string(index=False))
    print(f"  planted SKUs:    {sorted(defect)}")
    print(f"  discovered SKUs: {sorted(found)}")
    print(f"  match: {'YES' if found == defect else 'NO'}")

    dref = X[X.sku.isin(defect)]
    compare("F1 defect-SKU CM2", dref.cm2.sum(), float(worst.cm2.sum()),
            tolerance=TOLERANCE_IMPUTED)
    compare("F1 defect-SKU CM1", dref.cm1.sum(), float(worst.cm1.sum()),
            tolerance=TOLERANCE_IMPUTED)

    # ---- Finding 3: channel economics -----------------------------------
    ch = q(conn, f"""
        select acquisition_channel_key as channel,
               sum(net_revenue)  as net_revenue,
               sum(ad_spend)     as ad_spend,
               sum(cm2)          as cm2,
               sum(cm3)          as cm3
        from {m}.fct_channel_economics_monthly
        group by 1 order by 1
    """).set_index("channel")
    aff_ref = Y[Y.acquisition_channel == "Affiliate"]
    spend_ref = ref["ad_spend"]
    compare("F3 Affiliate CM2", aff_ref.cm2.sum(), float(ch.loc["Affiliate", "cm2"]),
            tolerance=TOLERANCE_IMPUTED)
    compare("F3 Affiliate ad spend",
            spend_ref[spend_ref.channel == "Affiliate"].spend.sum(),
            float(ch.loc["Affiliate", "ad_spend"]))
    compare("F3 total ad spend", spend_ref.spend.sum(), float(ch.ad_spend.sum()))

    # ---- Quarantine: what the pipeline consciously set aside ------------
    orph = q(conn, f"""
        select count(*) as n, coalesce(sum(refund_amount), 0) as amt
        from analytics_int.int_returns_orphaned
    """).iloc[0]
    dedup = q(conn, f"""
        select count(*) as n from analytics_int.int_orders_conformed
        where was_duplicated
    """).iloc[0]
    fixed = q(conn, f"""
        select count(*) as n from {m}.fct_order_lines where price_was_corrected
    """).iloc[0]
    imputed = q(conn, f"""
        select count(*) as n from {m}.dim_product where unit_cost_is_imputed
    """).iloc[0]

    print("\nDefect handling, as resolved by the pipeline:")
    print(f"  CM2 overstated by quarantine    "
          f"${quarantine_cm2_overstatement:>10,.0f}  "
          f"({quarantine_cm2_overstatement / X.cm2.sum():.2%} of CM2)")
    print(f"  duplicate orders removed        {int(dedup.n):>7,}")
    print(f"  price typos corrected           {int(fixed.n):>7,}")
    print(f"  unit costs imputed (SKU vers.)  {int(imputed.n):>7,}")
    print(f"  returns quarantined             {int(orph.n):>7,}  "
          f"(${float(orph.amt):,.0f} of refunds excluded)")

    conn.close()

    # ---- Report ---------------------------------------------------------
    out = pd.DataFrame(_rows)
    print("\n" + "=" * 84)
    print("RECONCILIATION: generator truth vs pipeline output")
    print("=" * 84)
    for _, r in out.iterrows():
        val_ref = (f"{r.reference:>14,.0f}" if r.unit == "rows"
                   else f"${r.reference:>13,.2f}")
        val_pipe = (f"{r.pipeline:>14,.0f}" if r.unit == "rows"
                    else f"${r.pipeline:>13,.2f}")
        mark = " " if r.status == "PASS" else ">"
        print(f"{mark} [{r.status}] {r.metric:<26} {val_ref}  {val_pipe}  "
              f"{r.variance_pct:+.3%}")

    failed = int((out.status == "FAIL").sum())
    print(f"\n{len(out) - failed}/{len(out)} metrics reconcile "
          f"(exact class {TOLERANCE_EXACT:.2%}, imputed class {TOLERANCE_IMPUTED:.2%})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
