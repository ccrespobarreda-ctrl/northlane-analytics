# DAX Measure Library

Every measure in the dashboard, with the reasoning behind it. Paste into Power BI
as a single calculation group or as individual measures.

**Validate against [`golden_values.md`](golden_values.md)** before building any
visual. If `[CM2]` does not return `$2,358,764` for FY2025, something is wrong
with the model and no amount of visual polish will fix it.

Two conventions used throughout:

- **`DIVIDE()`, never `/`.** A zero-spend month must return blank, not an error
  that poisons an entire column.
- **Explicit table references** on every column. `SUM(fct_order_lines[cm2])`,
  not `SUM([cm2])`.

---

## 1. Base measures — additive facts

`cm1` and `cm2` are precomputed at line grain in the warehouse and are fully
additive, so summing them is correct at every level of aggregation. Recomputing
the waterfall in DAX would duplicate business logic in two places, which is how
a dashboard and a SQL query start disagreeing.

```dax
Gross Revenue = SUM(fct_order_lines[gross_revenue])
Discount = SUM(fct_order_lines[discount])
Refunds = SUM(fct_order_lines[refund_amount])

-- Revenue after discounts but BEFORE returns. Used for AOV, because AOV is the
-- value of an order at the moment it was placed.
Discounted Revenue = SUM(fct_order_lines[discounted_revenue])

-- "Net revenue" in DTC means after discounts AND returns. This is the
-- denominator for every margin percentage. Using the pre-return figure
-- understates all three margins by roughly 8 points.
Net Revenue = SUM(fct_order_lines[net_revenue])

COGS = SUM(fct_order_lines[cogs])
COGS Recovered = SUM(fct_order_lines[cogs_recovered])

Shipping Revenue = SUM(fct_order_lines[shipping_revenue])
Shipping Cost = SUM(fct_order_lines[shipping_cost])
Payment Fees = SUM(fct_order_lines[payment_fee])
Pick Pack Cost = SUM(fct_order_lines[pick_pack_cost])
Return Shipping Cost = SUM(fct_order_lines[return_shipping_cost])
Restock Labor Cost = SUM(fct_order_lines[restock_labor_cost])

Fulfillment Cost =
    [Shipping Cost] + [Payment Fees] + [Pick Pack Cost]
    + [Return Shipping Cost] + [Restock Labor Cost]
    - [Shipping Revenue]

CM1 = SUM(fct_order_lines[cm1])
CM2 = SUM(fct_order_lines[cm2])

Orders = DISTINCTCOUNT(fct_order_lines[order_id])
Units = SUM(fct_order_lines[quantity])
Units Returned = SUM(fct_order_lines[units_returned])
Customers = DISTINCTCOUNT(fct_order_lines[customer_key])
```

---

## 2. Ad spend and CM3

**CM3 is only valid at channel grain.** Ad spend has no state, SKU, or category,
so a naive `[CM2] - [Ad Spend]` sliced by category silently returns CM2 minus
*all* spend for every row. The guard below returns blank instead of a
plausible-looking lie.

```dax
Ad Spend = SUM(fct_ad_spend[spend])
Platform Reported Revenue = SUM(fct_ad_spend[platform_reported_revenue])

-- Blank unless the current filter context is one ad spend can actually be
-- attributed to. Removing this guard is how a "CM3 by state" chart gets built.
CM3 =
VAR SpendIsAttributable =
    ISFILTERED(dim_channel[channel_name])
        || NOT (ISFILTERED(dim_geography[state_code])
                || ISFILTERED(dim_product[category])
                || ISFILTERED(dim_product[sku]))
RETURN
    IF(SpendIsAttributable, [CM2] - [Ad Spend])

CM3 Margin % = DIVIDE([CM3], [Net Revenue])
```

---

## 3. Margin ratios

Denominator is **`[Net Revenue]`** — after discounts and returns — throughout.
`[Discounted Revenue]` is used only for AOV, because an order's value is what the
customer paid at checkout, not what they kept.

```dax
CM1 Margin % = DIVIDE([CM1], [Net Revenue])
CM2 Margin % = DIVIDE([CM2], [Net Revenue])
Discount Rate = DIVIDE([Discount], [Gross Revenue])

AOV = DIVIDE([Discounted Revenue], [Orders])
CM2 per Order = DIVIDE([CM2], [Orders])
CM2 per Unit = DIVIDE([CM2], [Units])
```

---

## 4. Returns

Unit-based and dollar-based return rates answer different questions and will not
match. Accessories return rarely but cheaply; outerwear returns often and
expensively.

```dax
Unit Return Rate = DIVIDE([Units Returned], [Units])
Dollar Return Rate = DIVIDE([Refunds], [Gross Revenue])

-- The true cost of a return: the refund, minus what was recovered from resale,
-- plus the cost of getting it back and putting it away.
Return Margin Impact =
    [Refunds] - [COGS Recovered] + [Return Shipping Cost] + [Restock Labor Cost]

Cost per Return = DIVIDE([Return Margin Impact], [Units Returned])

-- Diagnostic for Finding 1. Sizing-driven returns point at a supplier
-- tolerance problem; "changed mind" points at merchandising.
Size Reason Share =
DIVIDE(
    CALCULATE(
        COUNTROWS(fct_returns),
        fct_returns[return_reason] IN {"size_too_small", "size_too_large"}
    ),
    CALCULATE(COUNTROWS(fct_returns))
)
```

---

## 5. Marketing efficiency

```dax
-- The CFO's number: all revenue over all spend, organic included.
MER = DIVIDE([Net Revenue], [Ad Spend])

-- What the platform claims. Only ever used to compare campaigns WITHIN a
-- channel; never to size a budget.
Platform ROAS = DIVIDE([Platform Reported Revenue], [Ad Spend])

-- What actually happened.
True ROAS = DIVIDE([Net Revenue], [Ad Spend])

-- The size of the platform's self-flattery. This is a finding, not noise.
Attribution Overstatement % =
    DIVIDE([Platform Reported Revenue] - [Net Revenue], [Net Revenue])

New Customers =
    CALCULATE(
        DISTINCTCOUNT(fct_order_lines[customer_key]),
        fct_order_lines[is_first_order] = TRUE()
    )

nCAC = DIVIDE([Ad Spend], [New Customers])

-- The single most useful marketing measure in the model: a channel can have
-- excellent ROAS and negative CM3 ROAS at the same time.
CM3 ROAS = DIVIDE([CM3], [Ad Spend])
```

---

## 6. Retention and LTV

These measures run against `fct_customer_cohorts`, which sits at a different
grain from the main star. See [`data_model.md`](data_model.md) — it is
deliberately **not** related to `dim_date`.

```dax
Cohort Customers = MAX(fct_customer_cohorts[cohort_customers])
Active Customers = SUM(fct_customer_cohorts[active_customers])
Retention Rate = DIVIDE([Active Customers], [Cohort Customers])

-- LTV in contribution margin, never revenue. Revenue LTV ignores that the
-- second order may have shipped free to Zone 8 and half returned.
Cohort CM2 = SUM(fct_customer_cohorts[cm2])

CM2 LTV per Customer = DIVIDE([Cohort CM2], [Cohort Customers])

-- Cumulative across months_since_first, which is what an LTV curve actually is.
Cumulative CM2 LTV =
VAR CurrentMonth = MAX(fct_customer_cohorts[months_since_first])
RETURN
    CALCULATE(
        [CM2 LTV per Customer],
        ALL(fct_customer_cohorts[months_since_first]),
        fct_customer_cohorts[months_since_first] <= CurrentMonth
    )

-- Guard against plotting cohorts that have not lived long enough. A four-month
-- old cohort on a twelve-month LTV curve looks like a collapse; it is just
-- young. This is the most common error in cohort analysis.
Cumulative CM2 LTV (Complete Only) =
    IF(
        SELECTEDVALUE(fct_customer_cohorts[is_complete_window]) = TRUE(),
        [Cumulative CM2 LTV]
    )

LTV to CAC = DIVIDE([Cumulative CM2 LTV], [nCAC])
```

---

## 7. Time intelligence

`dim_date` must be marked as the date table (Modeling → Mark as Date Table) or
none of these behave correctly.

```dax
Net Revenue LY =
    CALCULATE([Net Revenue], SAMEPERIODLASTYEAR(dim_date[date_day]))

Net Revenue YoY % =
    DIVIDE([Net Revenue] - [Net Revenue LY], [Net Revenue LY])

CM3 LY = CALCULATE([CM3], SAMEPERIODLASTYEAR(dim_date[date_day]))

-- CM3 margin compression is the headline of the memo: revenue up 46%,
-- CM3 margin down from 14.6% to 10.3%. This measure is the evidence.
CM3 Margin YoY (pp) =
    [CM3 Margin %] - CALCULATE([CM3 Margin %], SAMEPERIODLASTYEAR(dim_date[date_day]))

Net Revenue YTD = TOTALYTD([Net Revenue], dim_date[date_day])
CM2 YTD = TOTALYTD([CM2], dim_date[date_day])
```

---

## 8. Data quality disclosure

Put these on the Executive Summary. A client who finds the gap themselves later
trusts the whole dashboard less than one who is told upfront.

```dax
Imputed Cost Lines =
    CALCULATE(COUNTROWS(fct_order_lines), fct_order_lines[unit_cost_is_imputed] = TRUE())

Corrected Price Lines =
    CALCULATE(COUNTROWS(fct_order_lines), fct_order_lines[price_was_corrected] = TRUE())

-- Hard-coded from the reconciliation harness rather than modeled, because the
-- quarantined rows are by definition absent from the fact table. Sourced from
-- src/reconcile_marts.py output; update if the source defect rate changes.
Quarantined Refunds = 33868

Quarantine Overstatement % = DIVIDE(25222, [CM2])

DQ Disclosure =
    "Excludes " & FORMAT([Quarantined Refunds], "$#,##0") &
    " of unmatched returns (CM2 overstated " &
    FORMAT([Quarantine Overstatement %], "0.00%") & ")"
```

---

## 9. Conditional formatting helpers

Used to make the two loss-making SKUs jump out of the Product Profitability
matrix without a written explanation.

```dax
CM2 Color =
    SWITCH(TRUE(),
        [CM2 Margin %] < 0,    "#C0392B",
        [CM2 Margin %] < 0.10, "#E67E22",
        [CM2 Margin %] < 0.25, "#7F8C8D",
        "#1E8449"
    )

-- A SKU that makes money on the product and loses it on delivery. This is the
-- exact pattern the team's current reporting cannot see.
Margin Inversion Flag =
    IF([CM1] > 0 && [CM2] < 0, "CM1 positive / CM2 negative")
```
