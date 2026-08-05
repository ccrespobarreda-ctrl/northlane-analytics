{#
  The CASH view of returns: grain is one return record, dated by return_date.

  This model and fct_order_lines will NOT reconcile, and that is the point.
  fct_order_lines attributes a refund to the month of the original sale
  (was the sale profitable?); this model attributes it to the month the money
  left the business (what happened to cash?). Reporting one number for both
  questions is how a December cohort looks profitable and January looks broken.
#}
select
    r.return_id,
    r.order_line_key,
    r.order_id,
    r.sku,
    to_char(r.return_date, 'YYYYMMDD')::int             as return_date_key,
    to_char(r.original_order_date, 'YYYYMMDD')::int     as original_order_date_key,
    r.return_date,
    r.original_order_date,
    (r.return_date - r.original_order_date)             as days_to_return,
    l.product_key,
    l.category,
    l.geography_key,
    l.acquisition_channel_key,
    r.quantity_returned,
    r.refund_amount,
    r.cogs_recovered,
    r.return_shipping_cost,
    r.restock_labor_cost,
    r.return_reason,
    r.restocked,
    r.disposition,
    round(r.refund_amount - r.cogs_recovered
          + r.return_shipping_cost + r.restock_labor_cost, 2)
                                                        as return_margin_impact
from {{ ref('stg_returns') }} r
inner join {{ ref('fct_order_lines') }} l
    on l.order_line_key = r.order_line_key
