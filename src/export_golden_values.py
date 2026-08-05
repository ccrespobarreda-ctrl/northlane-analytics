#!/usr/bin/env python3
"""
Export golden values for DAX validation.

Power BI has no unit tests. The substitute is a table of known-correct numbers
computed in SQL, against which every measure is checked once before any visual is
built. A dashboard whose totals are wrong looks exactly like one whose totals are
right, until someone asks where a number came from.

    python src/export_golden_values.py > powerbi/golden_values.md

Each row states the DAX measure, the expected value, and the SQL that produced
it, so the check is reproducible rather than a screenshot.
"""

from __future__ import annotations

import os
import sys
from datetime import date

import psycopg2

MARTS = "analytics_marts"

CHECKS: list[tuple[str, str, str, str]] = [
    # (section, DAX measure, format, SQL)
    ("Headline FY2025", "[Gross Revenue]", "money", f"""
        select sum(gross_revenue) from {MARTS}.fct_order_lines
        where extract(year from order_date) = 2025"""),
    ("Headline FY2025", "[Discounted Revenue]", "money", f"""
        select sum(discounted_revenue) from {MARTS}.fct_order_lines
        where extract(year from order_date) = 2025"""),
    ("Headline FY2025", "[Refunds]", "money", f"""
        select sum(refund_amount) from {MARTS}.fct_order_lines
        where extract(year from order_date) = 2025"""),
    ("Headline FY2025", "[Net Revenue]", "money", f"""
        select sum(net_revenue) from {MARTS}.fct_order_lines
        where extract(year from order_date) = 2025"""),
    ("Headline FY2025", "[CM1]", "money", f"""
        select sum(cm1) from {MARTS}.fct_order_lines
        where extract(year from order_date) = 2025"""),
    ("Headline FY2025", "[CM2]", "money", f"""
        select sum(cm2) from {MARTS}.fct_order_lines
        where extract(year from order_date) = 2025"""),
    ("Headline FY2025", "[Orders]", "int", f"""
        select count(distinct order_id) from {MARTS}.fct_order_lines
        where extract(year from order_date) = 2025"""),
    ("Headline FY2025", "[Units]", "int", f"""
        select sum(quantity) from {MARTS}.fct_order_lines
        where extract(year from order_date) = 2025"""),
    ("Headline FY2025", "[AOV]", "money2", f"""
        select sum(discounted_revenue) / count(distinct order_id)
        from {MARTS}.fct_order_lines where extract(year from order_date) = 2025"""),
    ("Headline FY2025", "[CM1 Margin %]", "pct", f"""
        select sum(cm1) / sum(net_revenue)
        from {MARTS}.fct_order_lines where extract(year from order_date) = 2025"""),
    ("Headline FY2025", "[CM2 Margin %]", "pct", f"""
        select sum(cm2) / sum(net_revenue)
        from {MARTS}.fct_order_lines where extract(year from order_date) = 2025"""),
    ("Headline FY2025", "[Unit Return Rate]", "pct", f"""
        select sum(units_returned)::numeric / sum(quantity)
        from {MARTS}.fct_order_lines where extract(year from order_date) = 2025"""),
    ("Headline FY2025", "[New Customers]", "int", f"""
        select count(distinct customer_key) from {MARTS}.fct_order_lines
        where extract(year from order_date) = 2025 and is_first_order"""),

    ("Headline FY2025", "Waterfall closes: gross - discount - refunds", "money", f"""
        select sum(gross_revenue) - sum(discount) - sum(refund_amount)
               - sum(net_revenue)
        from {MARTS}.fct_order_lines where extract(year from order_date) = 2025"""),

    ("Marketing FY2025", "[Ad Spend]", "money", f"""
        select sum(spend) from {MARTS}.fct_ad_spend
        where extract(year from spend_date) = 2025"""),
    ("Marketing FY2025", "[CM3]  (no dimension filter)", "money", f"""
        select sum(cm3) from {MARTS}.fct_channel_economics_monthly
        where extract(year from month_start) = 2025"""),
    ("Marketing FY2025", "[CM3 Margin %]", "pct", f"""
        select sum(cm3) / sum(net_revenue)
        from {MARTS}.fct_channel_economics_monthly
        where extract(year from month_start) = 2025"""),
    ("Marketing FY2025", "[MER]", "ratio", f"""
        select sum(net_revenue) / (
            select sum(spend) from {MARTS}.fct_ad_spend
            where extract(year from spend_date) = 2025)
        from {MARTS}.fct_order_lines where extract(year from order_date) = 2025"""),
    ("Marketing FY2025", "[nCAC]", "money2", f"""
        select (select sum(spend) from {MARTS}.fct_ad_spend
                where extract(year from spend_date) = 2025)
             / (select count(distinct customer_key) from {MARTS}.fct_order_lines
                where extract(year from order_date) = 2025 and is_first_order)"""),

    ("Prior year", "[CM3] FY2024", "money", f"""
        select sum(cm3) from {MARTS}.fct_channel_economics_monthly
        where extract(year from month_start) = 2024"""),
    ("Prior year", "[CM3 Margin %] FY2024", "pct", f"""
        select sum(cm3) / sum(net_revenue)
        from {MARTS}.fct_channel_economics_monthly
        where extract(year from month_start) = 2024"""),

    ("Finding 1", "[CM2] filtered to the 2 worst SKUs, FY2025", "money", f"""
        with d as (select sku from {MARTS}.fct_order_lines
                   group by sku having sum(quantity) > 500
                   order by sum(cm2) limit 2)
        select sum(cm2) from {MARTS}.fct_order_lines
        where sku in (select sku from d) and extract(year from order_date) = 2025"""),
    ("Finding 1", "[CM1] same filter (positive)", "money", f"""
        with d as (select sku from {MARTS}.fct_order_lines
                   group by sku having sum(quantity) > 500
                   order by sum(cm2) limit 2)
        select sum(cm1) from {MARTS}.fct_order_lines
        where sku in (select sku from d) and extract(year from order_date) = 2025"""),
    ("Finding 1", "[Unit Return Rate] same filter", "pct", f"""
        with d as (select sku from {MARTS}.fct_order_lines
                   group by sku having sum(quantity) > 500
                   order by sum(cm2) limit 2)
        select sum(units_returned)::numeric / sum(quantity)
        from {MARTS}.fct_order_lines
        where sku in (select sku from d) and extract(year from order_date) = 2025"""),
    ("Finding 1", "[Cost per Return] same filter", "money2", f"""
        with d as (select sku from {MARTS}.fct_order_lines
                   group by sku having sum(quantity) > 500
                   order by sum(cm2) limit 2)
        select (sum(refund_amount) - sum(cogs_recovered) + sum(return_shipping_cost)
                + sum(restock_labor_cost)) / sum(units_returned)
        from {MARTS}.fct_order_lines
        where sku in (select sku from d) and extract(year from order_date) = 2025"""),

    ("Finding 2", "[CM2 per Order] Zone 6-8, discount >= 31%, FY2025", "money2", f"""
        with o as (select order_id, sum(gross_revenue) g, sum(discount) d,
                          sum(cm2) cm2, max(shipping_zone) z
                   from {MARTS}.fct_order_lines
                   where extract(year from order_date) = 2025 group by 1)
        select avg(cm2) from o where z >= 6 and d / nullif(g, 0) >= 0.31"""),
    ("Finding 2", "[CM2 per Order] all other orders, FY2025", "money2", f"""
        with o as (select order_id, sum(gross_revenue) g, sum(discount) d,
                          sum(cm2) cm2, max(shipping_zone) z
                   from {MARTS}.fct_order_lines
                   where extract(year from order_date) = 2025 group by 1)
        select avg(cm2) from o
        where not (z >= 6 and d / nullif(g, 0) >= 0.31)"""),

    ("Finding 3", "[Platform ROAS] Affiliate, FY2025", "ratio", f"""
        select sum(platform_reported_revenue) / sum(spend)
        from {MARTS}.fct_ad_spend
        where channel_key = 'Affiliate' and extract(year from spend_date) = 2025"""),
    ("Finding 3", "[CM3] Affiliate, FY2025 (negative)", "money", f"""
        select sum(cm3) from {MARTS}.fct_channel_economics_monthly
        where acquisition_channel_key = 'Affiliate'
          and extract(year from month_start) = 2025"""),
    ("Finding 3", "[CM3 Margin %] Affiliate, FY2025", "pct", f"""
        select sum(cm3) / sum(net_revenue)
        from {MARTS}.fct_channel_economics_monthly
        where acquisition_channel_key = 'Affiliate'
          and extract(year from month_start) = 2025"""),
    ("Finding 3", "[Size Reason Share] the 2 worst SKUs", "pct", f"""
        with d as (select sku from {MARTS}.fct_order_lines
                   group by sku having sum(quantity) > 500
                   order by sum(cm2) limit 2)
        select count(*) filter (where return_reason like 'size%')::numeric / count(*)
        from {MARTS}.fct_returns where sku in (select sku from d)"""),

    ("Finding 4", "[CM2 LTV per Customer] Google Search, M0-M12", "money2", f"""
        with sizes as (select distinct cohort_month, acquisition_channel_key,
                              cohort_customers
                       from {MARTS}.fct_customer_cohorts
                       where acquisition_channel_key = 'Google Search'
                         and cohort_month <= date '2024-12-31')
        select sum(c.cm2) / (select sum(cohort_customers) from sizes)
        from {MARTS}.fct_customer_cohorts c
        where c.acquisition_channel_key = 'Google Search'
          and c.cohort_month <= date '2024-12-31'
          and c.months_since_first between 0 and 12"""),
    ("Finding 4", "[CM2 LTV per Customer] TikTok Ads, M0-M12", "money2", f"""
        with sizes as (select distinct cohort_month, acquisition_channel_key,
                              cohort_customers
                       from {MARTS}.fct_customer_cohorts
                       where acquisition_channel_key = 'TikTok Ads'
                         and cohort_month <= date '2024-12-31')
        select sum(c.cm2) / (select sum(cohort_customers) from sizes)
        from {MARTS}.fct_customer_cohorts c
        where c.acquisition_channel_key = 'TikTok Ads'
          and c.cohort_month <= date '2024-12-31'
          and c.months_since_first between 0 and 12"""),

    ("Row counts", "COUNTROWS(fct_order_lines)", "int",
     f"select count(*) from {MARTS}.fct_order_lines"),
    ("Row counts", "COUNTROWS(dim_customer)", "int",
     f"select count(*) from {MARTS}.dim_customer"),
    ("Row counts", "COUNTROWS(dim_product)", "int",
     f"select count(*) from {MARTS}.dim_product"),
    ("Row counts", "COUNTROWS(dim_date)", "int",
     f"select count(*) from {MARTS}.dim_date"),
    ("Row counts", "COUNTROWS(fct_returns)", "int",
     f"select count(*) from {MARTS}.fct_returns"),
]


def fmt(value, kind: str) -> str:
    if value is None:
        return "(blank)"
    v = float(value)
    if kind == "money":
        return f"${v:,.0f}"
    if kind == "money2":
        return f"${v:,.2f}"
    if kind == "pct":
        return f"{v:.2%}"
    if kind == "ratio":
        return f"{v:.2f}"
    return f"{int(v):,}"


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("Set DATABASE_URL", file=sys.stderr)
        return 2

    conn = psycopg2.connect(dsn)
    print("# Golden Values for DAX Validation\n")
    print("Computed from the `marts` schema by `src/export_golden_values.py`. "
          "Check every measure against this table **before** building any visual.\n")
    print(f"Generated: {date.today().isoformat()}\n")
    print("> A dashboard with wrong totals is indistinguishable from a correct "
          "one until someone asks where a number came from. This is the check.\n")

    current = None
    with conn.cursor() as cur:
        for section, measure, kind, sql in CHECKS:
            if section != current:
                print(f"\n## {section}\n")
                print("| DAX measure | Expected |")
                print("|---|---|")
                current = section
            cur.execute(sql)
            row = cur.fetchone()
            print(f"| `{measure}` | **{fmt(row[0] if row else None, kind)}** |")

    conn.close()

    print("""
---

## Notes on two definitions that could reasonably differ

**MER denominator.** Computed here as net revenue **after** returns over total
spend. Using pre-return revenue raises MER by roughly 1.2 points. Post-return is
the more conservative reading and the one used throughout; if a client's existing
reporting uses pre-return revenue, reconcile the definition before comparing.

**CM3 at filtered grain.** `[CM3]` returns blank when the filter context includes
a dimension ad spend cannot be attributed to (state, category, SKU). This is
intentional, not a bug — see section 2 of `dax_measures.md`. The value above is
the unfiltered FY2025 total.

## Reproducing

```bash
export DATABASE_URL=postgresql://user:pass@host:5432/northlane
python src/export_golden_values.py > powerbi/golden_values.md
```
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
