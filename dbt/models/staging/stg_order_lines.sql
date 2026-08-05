{#
  Order line. Note what is NOT trusted here:

  * product_name -- a free-text snapshot with inconsistent casing and
    abbreviations. Kept only for the data quality report; the canonical name
    comes from dim_product.
  * unit_cost / line_cogs -- a snapshot that may disagree with the SCD2
    dimension. Recomputed in int_order_lines_enriched from the cost version
    valid on the order date.
  * unit_price_gross -- contains decimal-point typos. Corrected in
    intermediate, where list_price is available to detect them.

  baseline_return_rate and return_uplift are generator parameters and are
  dropped outright: using them would be leakage.
#}
select
    order_line_key,
    order_id,
    line_number::int                                    as line_number,
    customer_key,
    {{ parse_mixed_date('order_date') }}                as order_date,
    sku,
    product_key,
    product_name                                        as product_name_source,
    category                                            as category_source,
    quantity::int                                       as quantity,
    unit_price_gross::numeric(12,2)                     as unit_price_gross_source,
    unit_cost::numeric(10,2)                            as unit_cost_source,
    line_gross_revenue::numeric(12,2)                   as line_gross_revenue_source,
    line_discount::numeric(12,2)                        as line_discount_source,
    line_net_revenue::numeric(12,2)                     as line_net_revenue_source,
    line_cogs::numeric(12,2)                            as line_cogs_source,
    nullif(discount_code, '')                           as discount_code,
    billable_weight_lbs::numeric(8,2)                   as billable_weight_lbs,
    shipping_revenue_alloc::numeric(10,2)               as shipping_revenue_alloc,
    shipping_cost_alloc::numeric(10,2)                  as shipping_cost_alloc,
    payment_fee_alloc::numeric(10,2)                    as payment_fee_alloc,
    pick_pack_alloc::numeric(10,2)                      as pick_pack_alloc
from {{ source('raw', 'raw_order_lines') }}
