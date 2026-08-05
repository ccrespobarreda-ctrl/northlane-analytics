{#
  Resolve missing unit costs.

  A handful of newly onboarded SKUs have no cost loaded. Three options were
  considered:

    1. Drop them            -> silently loses revenue; unacceptable.
    2. Treat cost as zero   -> inflates margin; the worst possible answer.
    3. Impute from the category's median cost ratio, and FLAG it.  <- chosen

  Option 3 keeps the revenue in the P&L, keeps the distortion bounded, and makes
  the assumption auditable. Every downstream margin model can filter on
  unit_cost_is_imputed to quantify the exposure.
#}
with base as (
    select * from {{ ref('stg_products') }}
),

category_cost_ratio as (
    select
        category,
        -- percentile_cont returns double precision; cast to numeric so that
        -- round(value, scale) resolves and money stays exact.
        percentile_cont(0.5) within group (order by unit_cost / list_price)::numeric
            as median_cost_ratio
    from base
    where unit_cost is not null
      and list_price > 0
    group by category
)

select
    b.product_key,
    b.sku,
    b.product_name,
    b.category,
    b.list_price,
    coalesce(b.unit_cost, round(b.list_price * r.median_cost_ratio, 2))
                                                        as unit_cost,
    b.unit_cost_missing                                 as unit_cost_is_imputed,
    b.weight_lbs,
    b.valid_from,
    b.valid_to,
    b.is_current
from base b
left join category_cost_ratio r on r.category = b.category
