{#
  SCD Type 2. One row per SKU cost version; product_key is the surrogate key
  that fact rows point at, so a fact row is permanently bound to the cost that
  was true when the sale happened.
#}
select
    product_key,
    sku,
    product_name,
    category,
    list_price,
    unit_cost,
    unit_cost_is_imputed,
    weight_lbs,
    valid_from,
    valid_to,
    is_current,
    round(1 - (unit_cost / nullif(list_price, 0)), 4)    as list_gross_margin_pct
from {{ ref('int_products_costed') }}
