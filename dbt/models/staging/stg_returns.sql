{#
  Return lines. Two date columns matter and they are not interchangeable:

    return_date          -- when cash left the business  (financial reporting)
    original_order_date  -- when the sale was made       (margin analysis)

  Both are kept. Choosing between them is an analytical decision, documented in
  docs/business_rules.md, not something staging should silently make.
#}
select
    return_id,
    nullif(order_line_key, '')                          as order_line_key,
    nullif(order_id, '')                                as order_id,
    sku,
    {{ parse_mixed_date('original_order_date') }}        as original_order_date,
    {{ parse_mixed_date('return_date') }}                as return_date,
    quantity_returned::int                              as quantity_returned,
    refund_amount::numeric(12,2)                        as refund_amount,
    return_reason,
    return_shipping_cost::numeric(10,2)                 as return_shipping_cost,
    restock_labor_cost::numeric(10,2)                  as restock_labor_cost,
    restocked::boolean                                  as restocked,
    disposition,
    cogs_recovered::numeric(12,2)                       as cogs_recovered
from {{ source('raw', 'raw_returns') }}
