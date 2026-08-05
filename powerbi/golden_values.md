# Golden Values for DAX Validation

Computed from the `marts` schema by `src/export_golden_values.py`. Check every measure against this table **before** building any visual.

Generated: 2026-08-05

> A dashboard with wrong totals is indistinguishable from a correct one until someone asks where a number came from. This is the check.


## Headline FY2025

| DAX measure | Expected |
|---|---|
| `[Gross Revenue]` | **$10,017,806** |
| `[Discounted Revenue]` | **$8,933,852** |
| `[Refunds]` | **$1,962,393** |
| `[Net Revenue]` | **$6,971,459** |
| `[CM1]` | **$3,862,903** |
| `[CM2]` | **$2,358,764** |
| `[Orders]` | **48,531** |
| `[Units]` | **97,359** |
| `[AOV]` | **$184.09** |
| `[CM1 Margin %]` | **55.41%** |
| `[CM2 Margin %]` | **33.83%** |
| `[Unit Return Rate]` | **19.31%** |
| `[New Customers]` | **34,000** |
| `Waterfall closes: gross - discount - refunds` | **$0** |

## Marketing FY2025

| DAX measure | Expected |
|---|---|
| `[Ad Spend]` | **$1,637,689** |
| `[CM3]  (no dimension filter)` | **$721,075** |
| `[CM3 Margin %]` | **10.34%** |
| `[MER]` | **4.26** |
| `[nCAC]` | **$48.17** |

## Prior year

| DAX measure | Expected |
|---|---|
| `[CM3] FY2024` | **$683,676** |
| `[CM3 Margin %] FY2024` | **14.56%** |

## Finding 1

| DAX measure | Expected |
|---|---|
| `[CM2] filtered to the 2 worst SKUs, FY2025` | **$-79,905** |
| `[CM1] same filter (positive)` | **$9,852** |
| `[Unit Return Rate] same filter` | **44.51%** |
| `[Cost per Return] same filter` | **$78.18** |

## Finding 2

| DAX measure | Expected |
|---|---|
| `[CM2 per Order] Zone 6-8, discount >= 31%, FY2025` | **$-2.93** |
| `[CM2 per Order] all other orders, FY2025` | **$50.44** |

## Finding 3

| DAX measure | Expected |
|---|---|
| `[Platform ROAS] Affiliate, FY2025` | **8.38** |
| `[CM3] Affiliate, FY2025 (negative)` | **$-18,284** |
| `[CM3 Margin %] Affiliate, FY2025` | **-3.29%** |
| `[Size Reason Share] the 2 worst SKUs` | **90.44%** |

## Finding 4

| DAX measure | Expected |
|---|---|
| `[CM2 LTV per Customer] Google Search, M0-M12` | **$108.42** |
| `[CM2 LTV per Customer] TikTok Ads, M0-M12` | **$47.64** |

## Row counts

| DAX measure | Expected |
|---|---|
| `COUNTROWS(fct_order_lines)` | **173,217** |
| `COUNTROWS(dim_customer)` | **72,000** |
| `COUNTROWS(dim_product)` | **540** |
| `COUNTROWS(dim_date)` | **1,096** |
| `COUNTROWS(fct_returns)` | **38,434** |

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

