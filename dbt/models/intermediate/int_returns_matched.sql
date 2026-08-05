{#
  Returns that resolve to a surviving order line.

  Aggregated to order-line grain here because a single line can generate more
  than one return record. Fanning out a fact table by joining un-aggregated
  returns to order lines is one of the most common margin-inflation bugs in
  e-commerce models: revenue gets double counted for every extra return row.
#}
select
    r.order_line_key,
    count(*)                                            as return_records,
    sum(r.quantity_returned)                            as units_returned,
    sum(r.refund_amount)                                as refund_amount,
    sum(r.cogs_recovered)                               as cogs_recovered,
    sum(r.return_shipping_cost)                         as return_shipping_cost,
    sum(r.restock_labor_cost)                          as restock_labor_cost,
    min(r.return_date)                                  as first_return_date,
    max(r.return_date)                                  as last_return_date,
    min(r.original_order_date)                          as original_order_date,
    bool_or(r.restocked)                                as any_restocked
from {{ ref('stg_returns') }} r
inner join {{ ref('int_order_lines_enriched') }} l
    on l.order_line_key = r.order_line_key
group by r.order_line_key
