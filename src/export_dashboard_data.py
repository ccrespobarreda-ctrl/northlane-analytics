#!/usr/bin/env python3
"""
Export the dashboard payload from the marts.

Emits a single JSON document consumed by docs/index.html. The HTML is built with
this data embedded rather than fetched, so the page works from file://, from
GitHub Pages, and from a phone with a bad connection, with no CORS or loading
state to get wrong.

    python src/export_dashboard_data.py > powerbi/dashboard_data.json

Every figure on the page traces to a query here. Nothing in the HTML is typed by
hand, which is the only way a dashboard stays true after a data refresh.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from decimal import Decimal

import psycopg2

M = "analytics_marts"
FY = 2025


def rows(cur, sql: str) -> list[dict]:
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    out = []
    for r in cur.fetchall():
        d = {}
        for c, v in zip(cols, r):
            d[c] = float(v) if isinstance(v, Decimal) else v
        out.append(d)
    return out


def one(cur, sql: str) -> dict:
    r = rows(cur, sql)
    return r[0] if r else {}


def build(cur) -> dict:
    # ---- Headline and waterfall -------------------------------------
    head = one(cur, f"""
        select
            sum(gross_revenue)                              as gross_revenue,
            sum(discount)                                   as discounts,
            sum(discounted_revenue)                         as discounted_revenue,
            sum(refund_amount)                              as refunds,
            sum(net_revenue)                                as net_revenue,
            sum(cogs) - sum(cogs_recovered)                 as cogs_net,
            sum(shipping_cost) + sum(payment_fee) + sum(pick_pack_cost)
              + sum(return_shipping_cost) + sum(restock_labor_cost)
              - sum(shipping_revenue)                       as fulfillment,
            sum(cm1)                                        as cm1,
            sum(cm2)                                        as cm2,
            count(distinct order_id)                        as orders,
            sum(quantity)                                   as units,
            sum(units_returned)::numeric / sum(quantity)    as unit_return_rate,
            sum(discounted_revenue) / count(distinct order_id) as aov
        from {M}.fct_order_lines
        where extract(year from order_date) = {FY}""")

    spend = one(cur, f"""
        select sum(spend) as ad_spend from {M}.fct_ad_spend
        where extract(year from spend_date) = {FY}""")

    head["ad_spend"] = spend["ad_spend"]
    head["cm3"] = head["cm2"] - head["ad_spend"]
    head["cm1_margin"] = head["cm1"] / head["net_revenue"]
    head["cm2_margin"] = head["cm2"] / head["net_revenue"]
    head["cm3_margin"] = head["cm3"] / head["net_revenue"]
    head["mer"] = head["net_revenue"] / head["ad_spend"]

    # ---- Three-year trend -------------------------------------------
    trend = rows(cur, f"""
        with l as (
            select extract(year from order_date)::int as yr,
                   sum(gross_revenue) gross, sum(net_revenue) net,
                   sum(cm1) cm1, sum(cm2) cm2,
                   count(distinct order_id) orders
            from {M}.fct_order_lines group by 1),
        s as (
            select extract(year from spend_date)::int as yr, sum(spend) spend
            from {M}.fct_ad_spend group by 1)
        select l.yr, l.gross, l.net, l.orders,
               round(l.cm1 / l.net, 4)                     as cm1_margin,
               round(l.cm2 / l.net, 4)                     as cm2_margin,
               round((l.cm2 - s.spend) / l.net, 4)         as cm3_margin,
               l.cm2 - s.spend                             as cm3
        from l join s using (yr) order by l.yr""")

    # ---- Margin bridge: where the CM3 decline came from --------------
    # A time series shows THAT margin fell. The first question a CFO or an
    # investor asks is which cost caused it, which needs a variance bridge:
    # each cost block expressed as a share of net revenue, then differenced.
    ratios = rows(cur, f"""
        select extract(year from f.order_date)::int                as yr,
               round(sum(f.discount) / sum(f.gross_revenue), 4)    as discount_rate,
               round(sum(f.refund_amount) / sum(f.gross_revenue), 4) as return_rate,
               round(avg(p.unit_cost / p.list_price), 4)           as unit_cost_ratio
        from {M}.fct_order_lines f
        join {M}.dim_product p on p.product_key = f.product_key
        group by 1 order by 1""")

    # ---- Monthly CM3 margin -----------------------------------------
    monthly = rows(cur, f"""
        with l as (
            select date_trunc('month', order_date)::date m,
                   sum(net_revenue) net, sum(cm2) cm2
            from {M}.fct_order_lines group by 1),
        s as (
            select date_trunc('month', spend_date)::date m, sum(spend) spend
            from {M}.fct_ad_spend group by 1)
        select to_char(l.m, 'YYYY-MM') as month,
               round((l.cm2 - coalesce(s.spend, 0)) / l.net, 4) as cm3_margin,
               round(l.cm2 / l.net, 4)                          as cm2_margin,
               l.net                                            as net_revenue
        from l left join s using (m) order by l.m""")

    # ---- Finding 1: SKU scatter -------------------------------------
    skus = rows(cur, f"""
        select f.sku, p.product_name, p.category,
               sum(f.quantity)                                  as units,
               sum(f.net_revenue)                               as net_revenue,
               round(sum(f.units_returned)::numeric
                     / sum(f.quantity), 4)                      as return_rate,
               round(sum(f.cm2) / sum(f.net_revenue), 4)        as cm2_margin,
               round(sum(f.cm1) / sum(f.net_revenue), 4)        as cm1_margin,
               sum(f.cm2)                                       as cm2
        from {M}.fct_order_lines f
        join {M}.dim_product p on p.product_key = f.product_key
        where extract(year from f.order_date) = {FY}
        group by 1, 2, 3
        having sum(f.quantity) >= 150
        order by sum(f.cm2) asc""")

    worst_skus = [s["sku"] for s in skus[:2]]

    f1 = one(cur, f"""
        select sum(quantity) units, sum(units_returned) returned,
               round(sum(units_returned)::numeric / sum(quantity), 4) return_rate,
               sum(net_revenue) net_revenue, sum(cm1) cm1, sum(cm2) cm2,
               round((sum(refund_amount) - sum(cogs_recovered)
                      + sum(return_shipping_cost) + sum(restock_labor_cost))
                     / sum(units_returned), 2) cost_per_return
        from {M}.fct_order_lines
        where extract(year from order_date) = {FY}
          and sku in ({','.join("'" + s + "'" for s in worst_skus)})""")

    f1_reasons = one(cur, f"""
        select round(100.0 * count(*) filter (where return_reason like 'size%')
                     / count(*), 1) as size_share
        from {M}.fct_returns
        where sku in ({','.join("'" + s + "'" for s in worst_skus)})""")

    f1_baseline = one(cur, f"""
        select round(sum(units_returned)::numeric / sum(quantity), 4) return_rate,
               round(sum(cm2) / sum(net_revenue), 4)                 cm2_margin
        from {M}.fct_order_lines
        where extract(year from order_date) = {FY}
          and sku not in ({','.join("'" + s + "'" for s in worst_skus)})""")

    f1_catalogue_size = one(cur, f"""
        select round(100.0 * count(*) filter (where return_reason like 'size%')
                     / count(*), 1) as size_share
        from {M}.fct_returns
        where sku not in ({','.join("'" + s + "'" for s in worst_skus)})""")

    # ---- Finding 2: zone gradient and discount x zone ---------------
    zones = rows(cur, f"""
        select g.shipping_zone                              as zone,
               count(distinct f.order_id)                   as orders,
               round(sum(f.cm2) / count(distinct f.order_id), 2) as cm2_per_order,
               round(sum(f.cm2) / sum(f.net_revenue), 4)    as cm2_margin,
               round(avg(f.shipping_cost), 2)               as avg_ship_cost_line
        from {M}.fct_order_lines f
        join {M}.dim_geography g on g.geography_key = f.geography_key
        where extract(year from f.order_date) = {FY}
        group by 1 order by 1""")

    matrix = rows(cur, f"""
        with o as (
            select order_id, sum(gross_revenue) g, sum(discount) d,
                   sum(cm2) cm2, max(shipping_zone) z
            from {M}.fct_order_lines
            where extract(year from order_date) = {FY}
            group by 1)
        select case when z <= 3 then 'Z2-Z3' when z <= 5 then 'Z4-Z5'
                    else 'Z6-Z8' end                        as zone_band,
               case when d / nullif(g, 0) < 0.13 then '0-12%'
                    when d / nullif(g, 0) < 0.25 then '13-24%'
                    when d / nullif(g, 0) < 0.31 then '25-30%'
                    else '31%+' end                         as discount_band,
               count(*)                                     as orders,
               round(avg(cm2), 2)                           as cm2_per_order
        from o group by 1, 2""")

    f2 = one(cur, f"""
        with o as (
            select order_id, sum(gross_revenue) g, sum(discount) d,
                   sum(cm2) cm2, max(shipping_zone) z
            from {M}.fct_order_lines
            where extract(year from order_date) = {FY}
            group by 1)
        select count(*) filter (where z >= 6 and d / nullif(g,0) >= 0.31) as deep_far_orders,
               round(avg(cm2) filter (where z >= 6 and d / nullif(g,0) >= 0.31), 2)
                                                                  as deep_far_cm2,
               round(avg(cm2) filter (where not (z >= 6 and d / nullif(g,0) >= 0.31)), 2)
                                                                  as other_cm2,
               count(*) filter (where d / nullif(g,0) >= 0.31)     as deep_orders,
               round(sum(g * (d / nullif(g,0) - 0.25))
                     filter (where d / nullif(g,0) >= 0.31), 0)    as recoverable_gross
        from o""")

    # ---- Finding 3: channel economics -------------------------------
    # Platform ROAS is reported on checkout value, so comparing it against a
    # ROAS computed on post-return revenue mixes two effects: the platform's
    # over-attribution and the customer's returns. Pulling discounted revenue
    # per channel lets the page separate them.
    checkout = rows(cur, f"""
        select acquisition_channel_key                       as channel,
               sum(discounted_revenue)                       as checkout_revenue
        from {M}.fct_order_lines
        where extract(year from order_date) = {FY}
        group by 1""")
    checkout_map = {r["channel"]: r["checkout_revenue"] for r in checkout}

    channels = rows(cur, f"""
        select c.acquisition_channel_key                     as channel,
               d.channel_type,
               d.is_paid_acquisition,
               sum(c.net_revenue)                            as net_revenue,
               sum(c.ad_spend)                               as ad_spend,
               sum(c.cm2)                                    as cm2,
               sum(c.cm3)                                    as cm3,
               round(sum(c.cm3) / sum(c.net_revenue), 4)     as cm3_margin,
               round(sum(c.platform_reported_revenue)
                     / nullif(sum(c.ad_spend), 0), 2)        as platform_roas,
               round(sum(c.net_revenue)
                     / nullif(sum(c.ad_spend), 0), 2)        as true_roas,
               round(sum(c.cm3) / nullif(sum(c.ad_spend), 0), 2) as cm3_roas,
               sum(c.new_customers)                          as new_customers,
               round(sum(c.ad_spend)
                     / nullif(sum(c.new_customers), 0), 2)   as ncac
        from {M}.fct_channel_economics_monthly c
        left join {M}.dim_channel d on d.channel_key = c.acquisition_channel_key
        where extract(year from c.month_start) = {FY}
        group by 1, 2, 3
        order by platform_roas desc nulls last""")

    for c in channels:
        c["checkout_revenue"] = checkout_map.get(c["channel"], 0.0)
        # Same denominator the platform uses, so the difference is purely
        # over-attribution rather than over-attribution plus returns.
        c["roas_checkout_basis"] = (
            round(c["checkout_revenue"] / c["ad_spend"], 2) if c["ad_spend"] else None)
        c["overattribution_pct"] = (
            round(c["platform_roas"] / c["roas_checkout_basis"] - 1, 4)
            if c["platform_roas"] and c["roas_checkout_basis"] else None)

    # ---- Finding 4: LTV vs CAC, complete cohorts only ---------------
    ltv = rows(cur, f"""
        with sizes as (
            select distinct cohort_month, acquisition_channel_key, cohort_customers
            from {M}.fct_customer_cohorts
            where cohort_month <= date '2024-12-31'),
        totals as (
            select acquisition_channel_key, sum(cohort_customers) as customers
            from sizes group by 1),
        cm as (
            select acquisition_channel_key, sum(cm2) as cm2, sum(orders) as orders
            from {M}.fct_customer_cohorts
            where cohort_month <= date '2024-12-31'
              and months_since_first between 0 and 12
            group by 1),
        cac as (
            select acquisition_channel_key,
                   sum(ad_spend) / nullif(sum(new_customers), 0) as ncac
            from {M}.fct_channel_economics_monthly
            where month_start <= date '2024-12-31'
            group by 1)
        select t.acquisition_channel_key                     as channel,
               t.customers,
               round(cm.cm2 / t.customers, 2)                as ltv_12m,
               round(cm.orders::numeric / t.customers, 2)    as orders_per_customer,
               round(cac.ncac, 2)                            as ncac,
               round((cm.cm2 / t.customers)
                     / nullif(cac.ncac, 0), 2)               as ltv_cac
        from totals t
        join cm  on cm.acquisition_channel_key = t.acquisition_channel_key
        left join cac on cac.acquisition_channel_key = t.acquisition_channel_key
        order by ltv_12m desc""")

    # ---- First-order economics, to separate two effects -------------
    # The LTV gap between channels has two components: the first order is worth
    # less, and the customer does not come back. Claiming the gap is "repeat
    # rate, not first-order size" is only half true unless both are measured.
    first_order = rows(cur, f"""
        select acquisition_channel_key                       as channel,
               round(avg(v.checkout), 2)                     as first_order_value,
               round(avg(v.cm2), 2)                          as first_order_cm2
        from (select customer_key, acquisition_channel_key,
                     sum(discounted_revenue) as checkout, sum(cm2) as cm2
              from {M}.fct_order_lines
              where is_first_order
              group by 1, 2) v
        group by 1""")

    # ---- LTV curves by month, for the retention chart ---------------
    curves = rows(cur, f"""
        with sizes as (
            select acquisition_channel_key, sum(cohort_customers) as customers
            from (select distinct cohort_month, acquisition_channel_key,
                         cohort_customers
                  from {M}.fct_customer_cohorts
                  where cohort_month <= date '2024-12-31') s
            group by 1)
        select c.acquisition_channel_key                     as channel,
               c.months_since_first                          as month,
               round(sum(sum(c.cm2)) over (
                   partition by c.acquisition_channel_key
                   order by c.months_since_first) / max(s.customers), 2)
                                                             as cum_ltv
        from {M}.fct_customer_cohorts c
        join sizes s on s.acquisition_channel_key = c.acquisition_channel_key
        where c.cohort_month <= date '2024-12-31'
          and c.months_since_first between 0 and 12
        group by c.acquisition_channel_key, c.months_since_first
        order by 1, 2""")

    # ---- Category table ---------------------------------------------
    categories = rows(cur, f"""
        select category,
               sum(quantity)                                 as units,
               sum(net_revenue)                              as net_revenue,
               round(sum(units_returned)::numeric / sum(quantity), 4) as return_rate,
               round(sum(cm1) / sum(net_revenue), 4)         as cm1_margin,
               round(sum(cm2) / sum(net_revenue), 4)         as cm2_margin
        from {M}.fct_order_lines
        where extract(year from order_date) = {FY}
        group by 1 order by cm2_margin""")

    # ---- Disclosures -------------------------------------------------
    dq = one(cur, f"""
        select (select count(*) from analytics_int.int_returns_orphaned)  as orphan_returns,
               (select coalesce(sum(refund_amount), 0)
                  from analytics_int.int_returns_orphaned)               as orphan_refunds,
               (select count(*) from {M}.fct_order_lines
                 where price_was_corrected)                              as price_corrections,
               (select count(*) from {M}.dim_product
                 where unit_cost_is_imputed)                             as imputed_costs,
               (select count(*) from analytics_int.int_orders_conformed
                 where was_duplicated)                                   as duplicates_removed,
               (select count(*) from {M}.fct_order_lines)                as fact_rows""")

    # ---- Recovery scenarios, computed not typed ---------------------
    outerwear_baseline = 0.22
    avoidable = f1["units"] * (f1["return_rate"] - outerwear_baseline)
    f1_recovery = avoidable * f1["cost_per_return"]

    conversion_loss = 0.18
    deep_cm2_total = sum(m["cm2_per_order"] * m["orders"] for m in matrix
                         if m["discount_band"] == "31%+")
    f2_recovery = (f2["recoverable_gross"] * (1 - conversion_loss)
                   - deep_cm2_total * conversion_loss)

    aff = next(c for c in channels if c["channel"] == "Affiliate")
    meta = next(c for c in channels if c["channel"] == "Meta Prospecting")
    f3_recovery = meta["cm3_margin"] * aff["net_revenue"] - aff["cm3"]

    findings = {
        # The target the recovery is computed against: the Outerwear category
        # baseline, not the catalog-wide norm. Quoting the catalog figure in the
        # recommendation while calculating on the category one is the kind of
        # mismatch a client checks.
        "f1_target_return_rate": outerwear_baseline,
        "f1_recovery": round(f1_recovery),
        "f1_avoidable_returns": round(avoidable),
        "f2_recovery": round(f2_recovery),
        "f3_recovery": round(f3_recovery),
        "total_recovery": round(f1_recovery + f2_recovery + f3_recovery),
    }
    findings["recovery_as_pct_of_cm3"] = findings["total_recovery"] / head["cm3"]

    def cost_blocks(t):
        """Each cost block as a share of net revenue. They sum to 1 - cm3_margin."""
        return {"product": 1 - t["cm1_margin"],
                "delivery": t["cm1_margin"] - t["cm2_margin"],
                "advertising": t["cm2_margin"] - t["cm3_margin"]}

    b_first, b_last = cost_blocks(trend[0]), cost_blocks(trend[-1])
    # Sign flipped: a cost block growing is a margin effect shrinking.
    bridge = [{"driver": k, "effect_pts": round(-(b_last[k] - b_first[k]), 4),
               "share_first": b_first[k], "share_last": b_last[k]}
              for k in ("product", "delivery", "advertising")]

    net_last = trend[-1]["net"]
    for b in bridge:
        b["effect_usd"] = round(b["effect_pts"] * net_last)

    margin_bridge = {
        "from_year": trend[0]["yr"], "to_year": trend[-1]["yr"],
        "from_margin": trend[0]["cm3_margin"], "to_margin": trend[-1]["cm3_margin"],
        "total_pts": round(trend[-1]["cm3_margin"] - trend[0]["cm3_margin"], 4),
        "total_usd": round((trend[-1]["cm3_margin"] - trend[0]["cm3_margin"]) * net_last),
        "cm3_at_prior_margin": round(trend[0]["cm3_margin"] * net_last),
        "drivers": bridge,
        "unit_cost_inflation": round(
            ratios[-1]["unit_cost_ratio"] / ratios[0]["unit_cost_ratio"] - 1, 4),
        "ratios": ratios,
    }

    return {
        "generated": date.today().isoformat(),
        "fiscal_year": FY,
        "headline": head,
        "trend": trend,
        "margin_bridge": margin_bridge,
        "monthly": monthly,
        "skus": skus,
        "worst_skus": worst_skus,
        "finding1": {**f1, "size_reason_share": f1_reasons["size_share"],
                     "catalogue_size_share": f1_catalogue_size["size_share"],
                     "baseline_return_rate": f1_baseline["return_rate"],
                     "baseline_cm2_margin": f1_baseline["cm2_margin"]},
        "zones": zones,
        "matrix": matrix,
        "finding2": f2,
        "channels": channels,
        "ltv": ltv,
        "first_order": first_order,
        "ltv_curves": curves,
        "categories": categories,
        "data_quality": dq,
        "findings": findings,
    }


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("Set DATABASE_URL", file=sys.stderr)
        return 2
    conn = psycopg2.connect(dsn)
    with conn.cursor() as cur:
        payload = build(cur)
    conn.close()
    json.dump(payload, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
