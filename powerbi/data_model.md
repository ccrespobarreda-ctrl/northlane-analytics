# Power BI Data Model & Page Specification

Build guide for the report layer on top of the `marts` schema.

---

## 1. Connection and storage

**Import mode**, not DirectQuery. The marts total roughly 200k rows — trivial for
the VertiPaq engine — and Import gives full DAX time intelligence, which
DirectQuery restricts. DirectQuery here would trade capability for a benefit the
dataset is too small to need.

Connect with the PostgreSQL connector (Get Data → PostgreSQL database). Older
Power BI Desktop builds require the Npgsql provider to be installed separately;
recent builds include it. Verify against current Microsoft documentation.

Load **only** these tables:

```
analytics_marts.dim_date
analytics_marts.dim_product
analytics_marts.dim_customer
analytics_marts.dim_geography
analytics_marts.dim_channel
analytics_marts.fct_order_lines
analytics_marts.fct_returns
analytics_marts.fct_ad_spend
analytics_marts.fct_channel_economics_monthly
analytics_marts.fct_customer_cohorts
```

Do **not** load `staging` or `intermediate`. They are implementation detail, and
loading them doubles the model size while inviting someone to build a visual on
an uncleaned view.

`fct_contribution_daily` is also excluded: it is a pre-aggregation for a dataset
large enough to need one, and this one is not. Keeping it would create two
sources of truth for the same numbers.

### Publishing constraint

Power BI Service does not accept consumer email domains (Gmail, Outlook.com,
iCloud) for sign-up. Publishing requires an organizational account, which in
practice means a custom domain with email — roughly $15–20/year.

If that is not in place, the workable alternative is a downloadable `.pbix` plus
a 90-second screen recording. For portfolio purposes the recording usually
converts better than a live link anyway: a reviewer watches a video and does not
install Power BI Desktop.

Scheduled refresh against a cloud Postgres typically still requires an
On-premises data gateway in Personal mode, since PostgreSQL is not a
cloud-native connector. Confirm current behavior before promising a client
automated refresh.

---

## 2. Star schema

```
                        ┌──────────────┐
                        │   dim_date   │
                        └──────┬───────┘
                               │ 1:*
      ┌──────────────┐         │         ┌──────────────┐
      │ dim_product  │──1:*────┼────*:1──│ dim_channel  │
      └──────────────┘         │         └──────────────┘
                        ┌──────▼───────────┐
      ┌──────────────┐  │ fct_order_lines  │  ┌──────────────────┐
      │ dim_customer │──│                  │──│  dim_geography   │
      └──────────────┘  └──────┬───────────┘  └──────────────────┘
                               │ 1:*
                        ┌──────▼───────┐      ┌──────────────┐
                        │ fct_returns  │      │ fct_ad_spend │
                        └──────────────┘      └──────┬───────┘
                                                     │ *:1
                                              dim_date, dim_channel

   Satellite tables (different grain, see §4):
      fct_channel_economics_monthly
      fct_customer_cohorts
```

### Relationships

| From | To | Cardinality | Direction | Active |
|---|---|---|---|---|
| `fct_order_lines[order_date_key]` | `dim_date[date_key]` | \*:1 | Single | Yes |
| `fct_order_lines[product_key]` | `dim_product[product_key]` | \*:1 | Single | Yes |
| `fct_order_lines[customer_key]` | `dim_customer[customer_key]` | \*:1 | Single | Yes |
| `fct_order_lines[geography_key]` | `dim_geography[geography_key]` | \*:1 | Single | Yes |
| `fct_order_lines[acquisition_channel_key]` | `dim_channel[channel_key]` | \*:1 | Single | Yes |
| `fct_returns[order_line_key]` | `fct_order_lines[order_line_key]` | \*:1 | Single | Yes |
| `fct_returns[return_date_key]` | `dim_date[date_key]` | \*:1 | Single | **No** |
| `fct_ad_spend[date_key]` | `dim_date[date_key]` | \*:1 | Single | Yes |
| `fct_ad_spend[channel_key]` | `dim_channel[channel_key]` | \*:1 | Single | Yes |

**Every relationship is single-direction.** Bidirectional cross-filtering is the
most common cause of ambiguous-path errors and of measures that silently return
different numbers depending on which visual they sit in. If a specific visual
needs cross-filtering, use `CROSSFILTER()` inside that measure rather than
changing the model.

**`fct_returns[return_date_key]` is inactive on purpose.** Returns reach
`dim_date` through `fct_order_lines`, giving the *original order date* — the
correct attribution for margin. The inactive relationship exists so a cash-flow
view can activate it explicitly:

```dax
Refunds (Cash Basis) =
    CALCULATE([Refunds], USERELATIONSHIP(fct_returns[return_date_key], dim_date[date_key]))
```

Two active paths from returns to the calendar would make every refund number
ambiguous. This is the single most important modeling decision in the report.

---

## 3. Model hygiene

**Mark as date table.** Select `dim_date`, Modeling → Mark as Date Table →
`date_day`. Without this, `SAMEPERIODLASTYEAR` and `TOTALYTD` misbehave in ways
that are hard to spot.

**Hide from report view** — every key column and every raw measure column:

| Table | Hide |
|---|---|
| `fct_order_lines` | all `*_key` columns, `order_id`, `line_number`, and every numeric column (they are surfaced only through measures) |
| `fct_returns` | `order_line_key`, `return_date_key`, `original_order_date_key` |
| `fct_ad_spend` | `ad_spend_key`, `date_key` |
| `dim_*` | the surrogate key columns |

Leaving raw numeric columns visible invites someone to drag `cm2` onto a canvas
and get an implicit `SUM` that bypasses every guard in the measure library. The
`[CM3]` guard in particular is useless if the underlying column is draggable.

**Set data categories:** `dim_geography[state_code]` → State or Province,
`dim_geography[state_name]` → State or Province. Required for the map visual to
resolve without ambiguity.

**Sort columns:** `dim_date[month_name]` sorted by `cal_month`, otherwise months
appear alphabetically. `dim_geography[shipping_zone_band]` sorted by
`shipping_zone`.

**Format measures once, in the model** — currency to 0 decimals, percentages to
1, ratios to 2. Formatting per-visual is how the same measure ends up displayed
three different ways in one report.

---

## 4. The two satellite tables

`fct_channel_economics_monthly` and `fct_customer_cohorts` sit at different grain
from `fct_order_lines` and are **deliberately not joined to `dim_date`**.

Wiring them into the main star would create ambiguity: a month-grain fact table
related to a day-grain calendar produces totals that are correct at month level
and meaningless at day level, with nothing on the canvas to indicate which the
user is looking at.

They are each used on exactly one page, with their own slicers:

- `fct_channel_economics_monthly` → Channel Economics page. Slice on its own
  `month_start` and `acquisition_channel_key`.
- `fct_customer_cohorts` → Retention page. Slice on `cohort_month`,
  `acquisition_channel_key`, `months_since_first`.

Relate both to `dim_channel` only. That relationship is unambiguous and lets the
channel slicer work consistently across pages.

---

## 5. Page specification

Five pages. Every visual title is written as the **question it answers**, not as
a description of its contents — `"Which categories lose money after returns?"`
rather than `"CM2 % by Category"`. A reader who has to work out what a chart is
for has already been failed by it.

### Page 1 — Executive Summary

*The page a client sees if they see only one.*

| Element | Spec | Golden value |
|---|---|---|
| KPI cards ×4 | `[Net Revenue]`, `[CM2 Margin %]`, `[CM3 Margin %]`, `[Unit Return Rate]` | $6,971,459 / 33.8% / 10.3% / 19.3% |
| Waterfall | Gross → discounts → returns → COGS → fulfillment → ad spend → CM3 | ends at $721,075 |
| Line chart | `[CM3 Margin %]` by month, with FY2024 comparison | 14.6% → 10.3% |
| Text box | The three findings with their dollar values | $201K total |
| Footer card | `[DQ Disclosure]` | $33,868 excluded |

The CM3 margin trend line *is* the argument: revenue up 46%, margin down 4.3
points. Put it above the fold.

### Page 2 — Product Profitability

*Where Finding 1 becomes self-evident.*

- **Scatter:** X = `[Net Revenue]`, Y = `[CM2 Margin %]`, size = `[Units]`,
  color = `[Unit Return Rate]`, one point per SKU. The two problem SKUs sit
  alone in the bottom-right quadrant — high revenue, negative margin. No
  annotation needed.
- **Matrix:** rows = category → SKU; columns = `[Units]`, `[Unit Return Rate]`,
  `[CM1 Margin %]`, `[CM2 Margin %]`, `[Cost per Return]`. Conditional
  formatting via `[CM2 Color]`.
- **Column chart:** `[Size Reason Share]` by SKU, top 10 by return volume. The
  defective SKUs read 90% against a 53% catalog norm.
- **Card:** `[Margin Inversion Flag]` count — SKUs with CM1 positive and CM2
  negative.

### Page 3 — Channel Economics

*Where Finding 3 becomes undeniable.*

- **Clustered bar:** `[Platform ROAS]` beside `[CM3 ROAS]` by channel, sorted by
  Platform ROAS descending. Affiliate first on one bar and last on the other, in
  the same visual. This is the whole finding in one image.
- **Table:** channel × `[Ad Spend]`, `[nCAC]`, `[MER]`, `[True ROAS]`,
  `[CM3]`, `[CM3 Margin %]`.
- **Column chart:** `[Attribution Overstatement %]` by channel — search ~8%,
  view-through social up to 100%.
- **Note:** state the spend-attribution rule on the canvas. Spend is credited to
  the acquisition channel including on repeat orders; correct for judging
  acquisition quality, wrong for judging this month's media buy.

### Page 4 — Geography

- **Filled map:** `[CM2 per Order]` by state. **Not** revenue — a revenue map
  shows where people live, not where money is made.
- **Column chart:** `[CM2 per Order]` by `shipping_zone`, ordered Z2→Z8. The
  monotonic decline from $56 to $40 is the shipping-cost gradient made visible.
- **Matrix:** shipping zone × discount band, values `[CM2 per Order]`. The
  Zone 6–8 / deep-discount cell reads **−$2.93** against $50.44 elsewhere.
  Finding 2, in one cell.
- **Disclosure text:** no CM3 on this page — ad spend is not reported by state,
  so a geographic CM3 would be an allocation presented as a measurement.

### Page 5 — Retention & Cohorts

- **Heatmap matrix:** rows = `cohort_month`, columns = `months_since_first`,
  values = `[Retention Rate]`. Filter `is_complete_window = TRUE`.
- **Line chart:** `[Cumulative CM2 LTV (Complete Only)]` by
  `months_since_first`, one line per acquisition channel. Google reaches $108 at
  M12; TikTok reaches $47.
- **Bar chart with reference line:** `[LTV to CAC]` by channel, constant line at
  1.0. TikTok (0.91) and Affiliate below it, visibly.
- **Note:** incomplete cohorts are excluded, not greyed out, and say so on the
  canvas. Plotting a four-month-old cohort on a twelve-month curve makes recent
  cohorts look like a collapse when they are merely young.

---

## 6. Before building any visual

Open the model, create the measures from
[`dax_measures.md`](dax_measures.md), and check each one against
[`golden_values.md`](golden_values.md).

Power BI has no unit tests. This table is the substitute, and it takes fifteen
minutes. A dashboard with wrong totals looks exactly like one with right totals
until a client asks where a number came from — and by then the credibility cost
has already been paid.
