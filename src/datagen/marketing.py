"""
Ad spend generation.

Spend is derived *backwards* from acquisitions: each new customer costs the
channel's CAC on the day they were acquired, inflated year over year for
auction pressure. That guarantees CAC and acquisition volume reconcile instead
of being two unrelated random series.

Affiliate is deliberately different. Its "spend" is a commission on attributed
revenue, so its platform ROAS is mechanically excellent (1 / commission rate)
while its true contribution is poor once the 20% discount code and the elevated
return rate are counted. That is Finding 3.

Every paid platform also over-reports revenue by 20-45%, reflecting overlapping
attribution windows. The gap between platform_reported_revenue and real order
revenue is itself a finding worth showing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C

_CAMPAIGNS = {
    "Google Search": [("gg_brand", "retargeting"), ("gg_nonbrand", "prospecting"),
                      ("gg_shopping", "prospecting"), ("gg_pmax", "prospecting")],
    "Meta Prospecting": [("fb_broad_video", "prospecting"), ("fb_lookalike", "prospecting"),
                         ("fb_advantage", "prospecting")],
    "Meta Retargeting": [("fb_dpa_cart", "retargeting"), ("fb_dpa_view", "retargeting")],
    "TikTok Ads": [("tt_spark_ugc", "prospecting"), ("tt_topview", "prospecting")],
    "Affiliate": [("aff_network", "prospecting")],
    "Email/Organic": [("klaviyo_flows", "retargeting")],
}

# Channel media benchmarks: (cpm, ctr)
_MEDIA = {
    "Google Search": (28.0, 0.041),
    "Meta Prospecting": (14.5, 0.011),
    "Meta Retargeting": (11.0, 0.019),
    "TikTok Ads": (9.5, 0.008),
    "Affiliate": (0.0, 0.0),
    "Email/Organic": (0.0, 0.0),
}

# Fixed monthly platform cost for owned channels (ESP subscription).
KLAVIYO_MONTHLY_COST = 1_450.0


def build_ad_spend(rng: np.random.Generator, cust: pd.DataFrame,
                   orders: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    # ---- New customers per (day, channel) --------------------------------
    acq = (cust.assign(d=pd.to_datetime(cust["first_order_date"]))
              .groupby(["d", "acquisition_channel"]).size()
              .rename("new_customers").reset_index())

    # ---- Revenue attributed to each channel per day ----------------------
    rev = (orders.assign(d=pd.to_datetime(orders["order_date"]))
                 .groupby(["d", "acquisition_channel"])["order_net_revenue"].sum()
                 .rename("attributed_revenue").reset_index())

    grid = acq.merge(rev, on=["d", "acquisition_channel"], how="outer").fillna(0.0)

    rows = []
    base_year = C.START_DATE.year

    for _, g in grid.iterrows():
        channel = g["acquisition_channel"]
        date = g["d"]
        share, base_cac, *_ = C.ACQUISITION_CHANNELS[channel]

        years_elapsed = (date.year - base_year) + (date.dayofyear / 365.0)
        inflation = (1.0 + C.CAC_ANNUAL_INFLATION) ** years_elapsed

        if channel == "Affiliate":
            spend = g["attributed_revenue"] * (
                C.AFFILIATE_COMMISSION_RATE + C.AFFILIATE_NETWORK_FEE_RATE)
        elif channel == "Email/Organic":
            spend = KLAVIYO_MONTHLY_COST / 30.4
        else:
            # Daily spend tracks acquisitions, plus a floor so spend never
            # drops to zero on days with no conversions.
            eff_cac = base_cac * inflation * rng.normal(1.0, 0.13)
            spend = max(g["new_customers"] * max(eff_cac, 1.0), base_cac * 1.8)

        if spend <= 0:
            continue

        camps = _CAMPAIGNS[channel]
        weights = rng.dirichlet(np.ones(len(camps)) * 3.0)
        cpm, ctr = _MEDIA[channel]

        for (cid, objective), wgt in zip(camps, weights):
            s = round(spend * wgt, 2)
            if s < 0.01:
                continue
            impressions = int(s / cpm * 1000) if cpm > 0 else 0
            clicks = int(impressions * ctr * rng.normal(1.0, 0.12)) if impressions else 0

            true_rev = g["attributed_revenue"] * wgt
            if cpm > 0:
                lo, hi = C.CHANNEL_ATTRIBUTION_INFLATION.get(
                    channel, C.PLATFORM_ATTRIBUTION_INFLATION)
                inflate = rng.uniform(lo, hi)
            elif channel == "Affiliate":
                # Last-click affiliate networks absorb credit for organic demand
                inflate = C.AFFILIATE_ATTRIBUTION_INFLATION * rng.normal(1.0, 0.05)
            else:
                inflate = 1.0
            reported_rev = round(true_rev * inflate, 2)

            rows.append({
                "date": date.date(),
                "channel": channel,
                "campaign_id": cid,
                "campaign_objective": objective,
                "spend": s,
                "impressions": impressions,
                "clicks": clicks,
                "platform_reported_conversions": int(
                    g["new_customers"] * wgt * inflate)
                    if (cpm > 0 or channel == "Affiliate") else 0,
                "platform_reported_revenue": reported_rev,
            })

    return pd.DataFrame(rows)
