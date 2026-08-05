# Business Rules

Analytical decisions that change reported numbers. They are written down so a
reader can disagree with a specific choice rather than distrust the whole model.

---

## Revenue

**The waterfall, and what "net revenue" means.**

```
gross revenue          list price x quantity
  - discounts
= discounted revenue   what the customer paid at checkout  -> AOV denominator
  - refunds
= net revenue          what the business kept              -> margin denominator
```

In DTC, "net revenue" means after discounts **and** returns. Using the
pre-return figure as a margin denominator understates CM1, CM2 and CM3 by
roughly 8 percentage points and produces margins that will not match any
industry benchmark. `discounted_revenue` exists as a separate column precisely
so the two are never confused: AOV uses it, margin percentages never do.

**Sales tax is excluded from revenue at every level.** Tax is collected on behalf
of the state; it is a liability, not income. It is carried through to
`stg_orders` so the transformation layer has to handle it explicitly, and it is
absent from `fct_order_lines` by design.

**Shipping revenue is revenue, and it sits in CM2, not CM1.** Charging for
shipping offsets a fulfillment cost, so netting it against COGS would flatter
product margin.

**Discounts reduce revenue; they are not a marketing expense.** Treating promo
codes as marketing spend would improve gross margin and worsen CAC — the same
money, moved to make two metrics lie in opposite directions.

**Cancelled-before-shipment orders are excluded entirely.** They are not
returns. Including them in return rate would overstate a fulfillment problem
that does not exist.

---

## Returns

**Two attribution rules, used for two different questions.**

| Question | Date used | Model |
|---|---|---|
| Was this sale profitable? | Original order date | `fct_order_lines` |
| What happened to cash this month? | Return date | `fct_returns` |

These two models **will not reconcile**, and that is correct. A December cohort's
returns arrive in January. Reporting one number for both questions makes
December look profitable and January look broken.

**COGS recovery depends on disposition.** Restocked units recover full cost;
liquidated units recover 25%; destroyed units recover nothing. Treating all
returns as full recovery is the single most common way apparel margin is
overstated.

**Return shipping and restock labor are real costs** and sit in CM2. A "free
returns" policy is not free.

---

## Contribution margin

| Level | Definition |
|---|---|
| **CM1** | Net revenue − refunds − COGS + COGS recovered |
| **CM2** | CM1 + shipping revenue − shipping cost − return shipping − payment fees − pick/pack − packaging − restock labor |
| **CM3** | CM2 − variable ad spend |

**CM3 exists only at channel grain.** Ad spend is not reported by state or by
SKU, so a state-level CM3 would be an allocation presented as a measurement.
`fct_contribution_daily` therefore stops at CM2, and CM3 lives only in
`fct_channel_economics_monthly`. This is a refusal to produce a number the data
cannot support.

**Wholesale is excluded from CM3** — it carries no variable acquisition cost.
It is reported separately.

---

## Cost allocation

Order-level costs are pushed down to line grain on these bases:

| Cost | Basis | Reasoning |
|---|---|---|
| Shipping | Billable weight share | Heavy items cause the cost |
| Payment fees | Value share | The fee is a percentage of value |
| Pick/pack, packaging | Unit share | Labor scales with units handled |

**Billable weight, not scale weight.** Carriers bill `max(actual, dimensional)`.
A boxed parka to Zone 8 costs multiples of a t-shirt to Zone 2, and category mix
drives shipping economics as much as order value does.

Any allocation is a modeling choice. An analyst who prefers to allocate
shipping by unit count instead of weight will get different SKU-level margins;
the basis is stated so that disagreement is possible.

---

## Marketing

**Acquisition channel is frozen at first order and never reassigned.** Every
cohort, LTV and CAC figure depends on this.

**Spend is credited to the acquisition channel, including on repeat orders.**
Correct for judging acquisition *quality*; wrong for judging this month's media
buy. Both readings are available in `fct_channel_economics_monthly`, and the
distinction is stated on the dashboard rather than assumed.

**Platform-reported revenue is retained but never used as revenue.** Platforms
over-credit themselves through overlapping attribution windows — in this dataset
by 8% (search) to 100% (view-through social). Both figures are shown side by
side; the gap is a finding, not noise to be cleaned away.

**MER uses net revenue (after returns) over total spend**, including organic.
It is the CFO's number. Note that some brands compute MER on pre-return revenue,
which raises it by roughly 1.2 points — reconcile the definition before
comparing against a client's existing reporting. Platform ROAS is only ever used to compare campaigns *within* a
channel.

---

## Customer metrics

**LTV is measured in CM2, never revenue.** Revenue LTV ignores that the second
order may have shipped free to Zone 8 and half returned.

**Repeat purchase rate requires an explicit window** — 12 months from first
order. Without one, the metric rises on its own as history accumulates and means
nothing.

**Incomplete cohorts are flagged, not plotted.** `is_complete_window` in
`fct_customer_cohorts` marks whether a cohort has actually lived long enough to
reach a given month. Plotting a four-month-old cohort on a twelve-month LTV
curve makes recent cohorts look like they are collapsing when they are merely
young. This is the most common error in cohort analysis.

**Exchanges are a return plus a new order**, flagged as such, and do **not**
count as a new customer.

---

## Geography and sales tax nexus

`shipping_zone` is the distance band from the Columbus, OH fulfillment center and
is the economically meaningful geographic attribute. A geography dimension
without it produces maps showing where customers live rather than where money is
made.

`has_state_sales_tax` and `nexus_threshold_usd` are **business modeling
attributes only**. Following *South Dakota v. Wayfair* (2018), states may
require remote sellers exceeding an economic threshold to collect sales tax;
most use $100,000 in annual sales, while California, Texas and New York use
$500,000, and several states have dropped the transaction-count test. Five
states have no statewide sales tax.

These figures change frequently and vary by product category — apparel is exempt
or partially exempt in several states, which this model does **not** attempt to
capture. **Nothing here constitutes tax advice.** The flags exist to support
commercial analysis of where nexus obligations are likely to arise, and any
actual filing decision requires a tax professional.
