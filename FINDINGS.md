# Measured Findings

Technical record. Every figure is produced by a script, not asserted by hand:

- `src/validate_findings.py` — generator self-test, **20/20 checks**
- `src/reconcile_marts.py` — pipeline vs ground truth, **15/15 metrics**
- `src/export_golden_values.py` — the values Power BI must reproduce

Client-facing version: [`docs/analysis_summary.md`](docs/analysis_summary.md)

---

## Revenue waterfall and margin structure

Margin denominators use **net revenue** — after discounts *and* returns, per DTC
convention. AOV uses discounted revenue, because an order is worth what the
customer paid at checkout.

| FY2025 | Value | % of net revenue |
|---|---|---|
| Gross revenue | $10,017,806 | — |
| less discounts | −$1,083,954 | |
| Discounted revenue | $8,933,852 | |
| less refunds | −$1,962,393 | |
| **Net revenue** | **$6,971,459** | — |
| CM1 (after COGS, net of recovery) | $3,862,903 | **55.4%** |
| CM2 (after fulfillment) | $2,358,764 | **33.8%** |
| CM3 (after ad spend) | $721,075 | **10.3%** |

| | 2023 | 2024 | 2025 |
|---|---|---|---|
| Orders | 16,847 | 32,922 | 48,531 |
| Gross revenue | $3.48M | $6.86M | $10.02M |
| AOV | $183.21 | $185.92 | $184.09 |
| CM1 margin | 59.3% | 57.6% | 55.4% |
| CM2 margin | 36.4% | 35.5% | 33.7% |
| **CM3 margin** | **14.8%** | **14.4%** | **10.2%** |
| Blended MER | 4.61 | 4.75 | 4.25 |

Margin structure is healthy against DTC benchmarks. The story is the **4.6-point
CM3 compression** while revenue tripled — growth bought rather than earned.

---

## Finding 1 — Two Outerwear SKUs sell at a loss after fulfillment

`Cascade Shell Parka Lite` (NL-OUT-0023) and `Cascade Windbreaker Pro`
(NL-OUT-0017).

| FY2025 | Defect SKUs | Rest of catalog |
|---|---|---|
| Units | 3,195 | 94,164 |
| Unit return rate | **44.5%** | 18.4% |
| Discounted revenue | $461,286 | $8.47M |
| CM1 | **+$9,852** | +$3.85M |
| CM2 | **−$79,905** | +$2.44M |
| Cost per return | $78.18 | — |

**90.4% of their returns cite sizing** versus 53.0% across the catalog — a
supplier tolerance defect, not a demand problem. The cliff is sharp: the
third-worst SKU by CM2 is *positive* at +$3,225.

- Fix sizing (44.5% → 22% Outerwear baseline): **+$56,227/yr**
- Delist instead: stops **$79,905/yr** of bleed, forfeits the revenue

## Finding 2 — Deep discounts shipped free to distant zones

CM2 per order, FY2025:

| | Zones 2–5 | Zones 6–8 |
|---|---|---|
| Normal discount | $56.76 | $48.29 |
| **Discount ≥31%** | $7.76 | **−$2.93** |

5,409 deep-discount orders produced $24,086 of CM2 in total. Three effects
compound: the discount, dimensional-weight shipping on bulky outerwear, and a
return rate that rises with discount depth. Free shipping applies regardless of
destination.

CM2 per order by zone shows the gradient cleanly: **$55.97 (Z2) → $40.31 (Z8)**.

- Cap discounts at 25%, 18% assumed conversion loss: **+$93,998/yr**

## Finding 3 — Affiliate: first on ROAS, last on contribution

FY2025:

| Channel | Net rev | Spend | Platform ROAS | True ROAS | CM3 | CM3 % |
|---|---|---|---|---|---|---|
| **Affiliate** | $555K | $112K | **8.38** | 4.98 | **−$18,284** | **−3.3%** |
| Google Search | $2.09M | $513K | 5.88 | 4.07 | $235,191 | +11.3% |
| Meta Prospecting | $1.87M | $545K | 5.88 | 3.43 | $109,681 | +5.9% |
| TikTok Ads | $794K | $356K | 5.46 | 2.23 | −$101,666 | −12.8% |

Mechanism: a 25% site-wide code, returns 32% above baseline, and last-click
attribution crediting the network for demand it did not create.

- Match Meta Prospecting's CM3 rate on the same revenue: **+$50,830/yr**

Secondary finding — platform overstatement: search reports 8–22% above true
revenue, view-through social up to 100%.

## Finding 4 — TikTok does not pay back

12-month CM2 LTV, complete cohorts only (acquired ≤ 2024-12-31):

| Channel | Customers | Orders/cust | 12M CM2 LTV | nCAC | LTV:CAC |
|---|---|---|---|---|---|
| Google Search | 8,245 | 1.88 | **$108.42** | $53.87 | **1.99** |
| Email/Organic | 4,228 | 1.60 | $94.19 | $8.18 | 11.37 |
| Meta Retargeting | 3,729 | 1.52 | $88.13 | $22.67 | 3.85 |
| Meta Prospecting | 10,649 | 1.34 | $72.59 | $45.75 | 1.57 |
| **TikTok Ads** | 6,166 | 1.08 | **$47.64** | $66.01 | **0.91** |
| Affiliate | 4,983 | 1.17 | $22.18 | $25.12 | 0.90 |

Google is worth **2.28×** TikTok. The gap is repeat rate (1.88 vs 1.08 orders),
not first-order size — a targeting problem, not a merchandising one.

Reallocation, not a saving. Requires an incrementality holdout before acting.

---

## Total

**$201,033/yr recoverable** across Findings 1–3, against FY2025 CM3 of
**$721,075** — **28% of contribution margin**, with no additional acquisition
spend.

---

## Disclosed limitations

| Item | Impact |
|---|---|
| 295 unmatched returns quarantined | CM2 overstated by $25,222 (**0.52%**) |
| 5 SKU costs imputed from category medians | COGS off by **0.004%** |
| Ad spend not reported by state | No geographic CM3 presented |
| Spend credited to acquisition channel on repeat orders | Measures acquisition quality, not current media efficiency |

Residual variance between pipeline and ground truth after all corrections:
**0.007% of CM2**, fully attributable to the imputed costs.
