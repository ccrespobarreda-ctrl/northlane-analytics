# Data Quality Report

Every defect below was found in the raw export, resolved in the transformation
layer, and quantified. Nothing was silently dropped.

The dollar figures come from `src/reconcile_marts.py`, which compares the
pipeline output against the generator's ground truth. Residual variance after all
corrections is **0.007% of CM2**, and every exact-match metric — row counts,
revenue, refunds, ad spend — agrees to the cent.

The harness uses two tolerance classes rather than one. Revenue and row counts
must survive cleaning untouched, so anything beyond float rounding is a defect
(0.01%). Cost-derived figures carry the known variance from five imputed unit
costs, so they get 0.1% — set just above the observed residual, not rounded up
for comfort. A single loose tolerance was tested by disabling the deduplication:
it let a **$42,457 revenue overstatement pass**, which is why the classes are
split. With them split, the same sabotage fails 11 of 15 metrics.

Worth noting what this catches that `dbt build` cannot: with deduplication
disabled, all 100 dbt tests still passed. Keys were still unique, referential
integrity still held, the revenue waterfall still closed. Internal consistency
and correctness are different properties.

---

## Summary

| # | Defect | Table | Rows | Resolution | Margin impact |
|---|---|---|---|---|---|
| 1 | Three date formats in one text column | orders, order_lines, returns | 48,873 | Parsed by pattern; unparseable values fail a `not_null` test | None |
| 2 | Inconsistent product names (case, whitespace, abbreviations) | order_lines | 38,300 | Line-level name discarded; canonical name from `dim_product` | None |
| 3 | State written three ways (`CA`, `California`, `ca.`) | orders | 8,816 | Normalised, then resolved via lookup against `stg_geography` | None |
| 4 | Untrimmed / uppercased emails | customers | 2,165 | Trimmed and lowercased before hashing | None |
| 5 | Duplicate orders (checkout retry) | orders, order_lines | 393 orders / 713 lines | Deduplicated on customer + date + totals | −$70,281 revenue correctly excluded |
| 6 | Orphaned returns (no order line) | returns | 295 | **Quarantined**, not deleted | CM2 overstated by **$25,222 (0.52%)** |
| 7 | Decimal-point typo in price feed | order_lines | 93 | Detected against `list_price`, divided by ten | Prevented ~$0.9M of phantom gross revenue |
| 8 | Missing `unit_cost` on new SKUs | products | 5 versions | Imputed from category median cost ratio, flagged | COGS off by **0.004%** |

---

## The three that actually matter

### Duplicate orders (#5)

A share of orders appear twice: same customer, same day, same totals, different
`order_id`. This is a checkout retry.

Counting both would overstate revenue, but the worse damage is to retention: one
customer becomes a repeat buyer, inflating repeat purchase rate and every
cohort curve built on it. A revenue error is visible; a retention error is not.

**Resolution.** Deduplicated on `(customer_key, order_date, order_gross_revenue,
order_net_revenue)`, keeping the lowest `order_id`.

**Stated limitation.** In a production system the tie-break would be
`created_at`. This export has no timestamp, so `order_id` is the only stable
ordering available. Two genuinely distinct orders from the same customer on the
same day for the same amount would be collapsed. At this volume the risk is
immaterial, but it is a real limitation, not a solved problem.

### Orphaned returns (#6)

295 return records have no resolvable order line — either the foreign key is
null or it points nowhere. Root cause in the source system: returns processed
through a channel that does not write back the originating line reference.

**Resolution.** Quarantined in `int_returns_orphaned`, excluded from margin
models, and reported. Deleting them would have been easier and would have
*improved* every margin number, which is precisely why it would have been wrong.

**Disclosed exposure.** $33,868 of refunds are excluded from the margin
waterfall, overstating CM2 by **$25,222 — 0.52%**. This is displayed on the
dashboard's Executive Summary rather than buried, because a client discovering
it later loses more trust than one told upfront.

### Decimal-point typos (#7)

93 lines carry a price ten times the product's list price.

Detection requires comparing against `list_price`, which needs a join — which is
why this correction lives in the intermediate layer, not staging. Left
uncorrected, these 93 rows would have added roughly **$0.9M of phantom gross
revenue** and made two categories look implausibly profitable.

After correction, `net_revenue = gross_revenue − discount` holds again, asserted
by `assert_net_revenue_identity`. That test is the real safeguard: it would fail
if the correction were applied to the wrong column or applied twice.

---

## Tests that guard the corrections

| Test | Catches |
|---|---|
| `assert_lines_reconcile_to_order_header` | Join fan-out *and* dropped lines, in one test |
| `assert_scd2_windows_do_not_overlap` | Duplicate cost versions silently doubling revenue |
| `assert_net_revenue_identity` | A price correction applied wrongly or twice |
| `assert_returns_are_plausible` | Returns before the sale, or beyond the 60-day window |
| `assert_orphan_returns_within_tolerance` | Quarantine growing past 2% of refund value (warn) |
| `not_null` on parsed dates | A fourth date format appearing in the source |

`dbt build` runs 100 models and tests. All pass.

---

## What is deliberately *not* used

Three columns in the raw export are latent parameters from the data generator:
`repeat_propensity`, `discount_affinity`, `return_uplift`. Alongside them,
`is_defect_sku` labels the problem SKUs directly.

None of these exist in a real business, and any finding derived from them would
be circular — the answer key, not an analysis. They are dropped in staging so no
downstream model can reach them. The two defective SKUs are identified from
their return behavior and CM2 alone, and
`src/reconcile_marts.py` confirms the pipeline rediscovers exactly the two SKUs
that were planted.
