{#
  The central fact table. Grain: one row per order line.

  CONTRIBUTION MARGIN WATERFALL
  Returns are joined pre-aggregated to line grain, so a line with three return
  records still produces exactly one fact row. Joining raw returns here would
  fan the table out and double-count revenue -- the single most common margin
  bug in e-commerce models.

  Returns are attributed to the ORIGINAL ORDER DATE, not the return date. That
  is the only way to answer "was this sale profitable". The cash view, which
  attributes refunds to the month the money left, is a separate model
  (fct_returns) and the two will not tie. That disagreement is correct and is
  documented in docs/business_rules.md.

  sales_tax is absent by design: it is collected on behalf of the state and is
  not revenue.
#}

with lines as (
    select * from {{ ref('int_order_lines_enriched') }}
),

returns as (
    select * from {{ ref('int_returns_matched') }}
),

first_orders as (
    select customer_key, first_order_id
    from {{ ref('int_customer_first_order') }}
),

combined as (
    select
        l.*,
        coalesce(r.units_returned, 0)                    as units_returned,
        coalesce(r.refund_amount, 0)                     as refund_amount,
        coalesce(r.cogs_recovered, 0)                    as cogs_recovered,
        coalesce(r.return_shipping_cost, 0)              as return_shipping_cost,
        coalesce(r.restock_labor_cost, 0)               as restock_labor_cost,
        (r.order_line_key is not null)                   as has_return,
        -- Carried at fact grain on purpose. Without it, every new-customer and
        -- CAC measure in Power BI would need an inactive relationship on
        -- dim_customer plus USERELATIONSHIP, which is harder to audit and
        -- silently breaks when someone adds a filter.
        (f.first_order_id = l.order_id)                  as is_first_order
    from lines l
    left join returns r on r.order_line_key = l.order_line_key
    left join first_orders f on f.customer_key = l.customer_key
)

select
    -- Keys
    order_line_key,
    order_id,
    line_number,
    to_char(order_date, 'YYYYMMDD')::int                 as order_date_key,
    order_date,
    customer_key,
    product_key,
    sku,
    category,
    state_code                                           as geography_key,
    acquisition_channel                                  as acquisition_channel_key,
    sales_channel,
    shipping_zone,
    discount_code,

    -- Volume
    quantity,
    units_returned,
    billable_weight_lbs,

    -- Revenue
    -- Industry-standard revenue waterfall. "Net revenue" in DTC means after
    -- discounts AND returns; using the pre-return figure as a margin
    -- denominator overstates the revenue base and understates every margin
    -- percentage by roughly 8 points.
    line_gross_revenue                                   as gross_revenue,
    line_discount                                        as discount,
    line_gross_revenue - line_discount                   as discounted_revenue,
    refund_amount,
    line_gross_revenue - line_discount - refund_amount   as net_revenue,
    discount_rate,

    -- Cost of goods
    line_cogs                                            as cogs,
    cogs_recovered,
    line_cogs - cogs_recovered                           as cogs_net_of_recovery,

    -- Fulfillment
    shipping_revenue_alloc                               as shipping_revenue,
    shipping_cost_alloc                                  as shipping_cost,
    payment_fee_alloc                                    as payment_fee,
    pick_pack_alloc                                      as pick_pack_cost,
    return_shipping_cost,
    restock_labor_cost,

    -- CM1: does the product make money?
    round(
        line_net_revenue - refund_amount - line_cogs + cogs_recovered
    , 2)                                                 as cm1,

    -- CM2: does DELIVERING the product make money?
    round(
        line_net_revenue - refund_amount - line_cogs + cogs_recovered
        + shipping_revenue_alloc
        - shipping_cost_alloc
        - payment_fee_alloc
        - pick_pack_alloc
        - return_shipping_cost
        - restock_labor_cost
    , 2)                                                 as cm2,

    -- Data quality lineage, carried into the mart on purpose so the dashboard
    -- can disclose its own exposure instead of implying false precision.
    has_return,
    is_first_order,
    unit_cost_is_imputed,
    price_was_corrected

from combined
