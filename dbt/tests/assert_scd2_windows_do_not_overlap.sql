-- A SKU must have exactly one valid cost version on any given date.
-- Overlapping windows make the range join in int_order_lines_enriched fan out,
-- silently duplicating revenue. This is invisible in aggregate and is the most
-- dangerous class of SCD2 bug.
select
    a.sku,
    a.product_key       as key_a,
    b.product_key       as key_b,
    a.valid_from        as from_a,
    a.valid_to          as to_a,
    b.valid_from        as from_b,
    b.valid_to          as to_b
from {{ ref('dim_product') }} a
join {{ ref('dim_product') }} b
    on a.sku = b.sku
   and a.product_key < b.product_key
   and a.valid_from <= b.valid_to
   and b.valid_from <= a.valid_to
