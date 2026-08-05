{#
  Two jobs: resolve state codes, and remove duplicate orders.

  DEDUPLICATION
  A small share of orders appear twice -- the same customer, same day, same
  totals, different order_id. This is a checkout retry, not two purchases.
  Counting both would overstate revenue and, worse, corrupt the repeat-purchase
  rate by turning one customer into a repeat buyer.

  The duplicate is identified on (customer_key, order_date, gross, net) and the
  lowest order_id is kept. In a production system the tie-break would be
  created_at; this source export has no timestamp, so order_id is the only
  stable ordering available. That limitation is stated rather than hidden.
#}
with state_lookup as (
    select state_code, state_code as lookup_key from {{ ref('stg_geography') }}
    union all
    select state_code, upper(state_name) from {{ ref('stg_geography') }}
),

resolved as (
    select
        o.*,
        sl.state_code                                   as state_code
    from {{ ref('stg_orders') }} o
    left join state_lookup sl on sl.lookup_key = o.state_text
),

flagged as (
    select
        *,
        row_number() over (
            partition by customer_key, order_date, order_gross_revenue, order_net_revenue
            order by order_id
        )                                               as dedupe_rank,
        count(*) over (
            partition by customer_key, order_date, order_gross_revenue, order_net_revenue
        )                                               as dedupe_group_size
    from resolved
)

select
    order_id,
    customer_key,
    order_seq,
    order_date,
    state_code,
    state_text                                          as state_code_source,
    acquisition_channel,
    sales_channel,
    shipping_zone,
    order_gross_revenue,
    order_net_revenue,
    order_units,
    order_billable_weight_lbs,
    shipping_revenue,
    shipping_cost,
    sales_tax,
    payment_fee,
    pick_pack_cost,
    (dedupe_group_size > 1)                             as was_duplicated
from flagged
where dedupe_rank = 1
