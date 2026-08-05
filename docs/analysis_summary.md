# FY2025 Contribution Margin — Analysis Summary

**Northlane Supply Co.** (fictional) · analysis by Cristina Crespo Barreda
Prepared February 2026 · figures reproduced from the warehouse by script

---

## Revenue waterfall

Revenue grew 46% in FY2025 to **$10.0M gross**, while contribution margin after
advertising fell from **14.6% to 10.3% of net revenue** — a 4.3-point compression
year over year, and 4.6 points since FY2023.

| FY2025 | Value | % of net revenue |
|---|---|---|
| Gross revenue | $10,017,806 | — |
| less discounts | −$1,083,954 | 10.8% of gross |
| less returns | −$1,962,393 | 19.6% of gross |
| **Net revenue** | **$6,971,459** | — |
| CM1, after cost of goods | $3,862,903 | 55.4% |
| CM2, after fulfillment | $2,358,764 | 33.8% |
| **CM3, after advertising** | **$721,075** | **10.3%** |

Margin structure is in line with DTC norms. The compression is concentrated
rather than general.

---

## Where the 4.6-point compression came from

Each cost block expressed as a share of net revenue, then differenced between
FY2023 and FY2025:

| Driver | Effect on CM3 | In dollars |
|---|---|---|
| Product cost | **−3.8 pts** | −$267,704 |
| Advertising | −1.9 pts | −$131,761 |
| Delivery | **+1.1 pts** | +$78,777 |
| | **−4.6 pts** | **−$320,687** |

Unit costs rose **10.7%** against list prices that did not change, while the
discount rate held steady (11.4% to 10.8%) and the return rate improved (21.6%
to 19.6%). The compression is a pass-through gap, not a promotional one.
Delivery moved the other way and is the one block that improved.

---

## Three concentrated leaks

### 1. Two Outerwear SKUs are loss-making after fulfillment

`Cascade Shell Parka Lite` and `Cascade Windbreaker Pro` returned at **44.5%**
against an 18.4% catalog norm; **90.4%** of those returns cite sizing versus 53%
elsewhere.

| | |
|---|---|
| Units sold, FY2025 | 3,195 |
| CM1, product margin | **+$9,852** |
| CM2, after fulfillment | **−$79,905** |
| Cost per return | $78.18 |
| Next-worst SKU in the catalog | +20.9% CM2 |

Both rank in the top 20 of 179 SKUs by revenue, so conventional sales reporting
shows them as successes. The loss appears only once freight, return shipping and
restocking are attributed.

**Sized:** at the 22% Outerwear category return rate, 719 returns a year would be
avoided at $78.18 each — **$56,227**. Removing them from the catalog would end
the $79,905 loss and also remove $260,886 of revenue.

### 2. Contribution collapses on deep discounts to distant zones

Contribution per order falls from **$55.97** in Zone 2 to **$40.31** in Zone 8 —
the freight gradient from the single Columbus, OH fulfillment center. Orders
discounted 31%+ and shipped to Zones 6–8 average **−$2.93** against $50.44
elsewhere, across 1,674 orders.

The calendar shows the same pattern. Across the three promotional windows —
Black Friday and the January and July clearances — CM3 margin averages **11.0%**
against **16.6%** in months with no promotion. November alone averages **1.5%**.

**Sized:** capping promotional depth at 25%, assuming an 18% conversion loss on
the affected orders, is worth **$93,998** a year.

### 3. Reported ROAS inverts against contribution by channel

| FY2025 | Platform ROAS | Same basis, measured | CM3 % |
|---|---|---|---|
| **Affiliate** | **8.38** | 7.14 | **−3.3%** |
| Google Search | 5.88 | 5.11 | +11.3% |
| Meta Prospecting | 5.88 | 4.35 | +5.9% |
| TikTok Ads | 5.46 | 3.03 | −12.8% |

Affiliate ranks first on the metric the platform reports and negative on
contribution after advertising. Two effects separate: 17% of its reported figure
is credit for demand it did not create, and a 25% site-wide code plus an elevated
return rate take the rest. On attribution alone TikTok is the larger distortion,
reporting **80%** above what it delivered.

**Sized:** at Meta Prospecting's CM3 rate on the same revenue, the affiliate gap
is worth **$50,830** a year.

---

## Customer economics by acquisition channel

12-month CM2 lifetime value, complete cohorts only (acquired through 2024):

| Channel | Customers | Orders/customer | 12M CM2 LTV | nCAC | LTV:CAC |
|---|---|---|---|---|---|
| Google Search | 8,245 | 1.88 | **$108.42** | $53.87 | **1.99** |
| Meta Retargeting | 3,729 | 1.52 | $88.13 | $22.67 | 3.85 |
| Meta Prospecting | 10,649 | 1.34 | $72.59 | $45.75 | 1.57 |
| **TikTok Ads** | 6,166 | 1.08 | **$47.64** | $51.88 | **0.91** |
| Affiliate | 4,983 | 1.17 | $22.18 | $24.13 | 0.90 |

First-order value is effectively identical between Google Search ($186.32) and
TikTok ($186.01), so the gap is not basket size: **84%** of it is repeat purchase
that does not happen. Reported ROAS cannot establish whether those sales would
have occurred without the spend, so any reallocation requires an incrementality
holdout to measure.

Email/Organic and Meta Retargeting sit above every paid channel but are not
budget levers — the email platform cost is fixed, and retargeting reaches only
visitors the paid channels already produced.

---

## Method and disclosures

Built from Shopify, Amazon and ad platform exports into a modeled warehouse:
36 months, 173,217 order lines. Unit costs are versioned, so margin is computed
against the cost in force on each order date. Returns are attributed to the
original order month for margin analysis, which will not tie to a cash view
attributing them to the refund date.

Three disclosures. **295 return records ($33,868)** could not be matched to an
order line and are excluded, overstating CM2 by **0.52%**. **Five SKU cost
versions** were imputed from category medians, affecting cost of goods by
**0.004%**. **Ad spend is not reported by state or SKU**, so no contribution
margin after advertising is presented at those grains.

A reconciliation harness compares every mart figure against the generator's
ground truth; residual variance is 0.007% of CM2, traceable to the imputed costs.

*Northlane Supply Co. is fictional and this dataset is synthetic. Every figure
above is reproducible from the repository.*
