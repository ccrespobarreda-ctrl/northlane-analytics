{#
  SCD Type 2 product dimension, one row per SKU cost version.

  valid_to is NULL on the current version. It is coerced to 9999-12-31 so that
  BETWEEN range joins downstream do not silently drop current-version rows --
  a classic and near-invisible SCD2 bug.

  unit_cost is NULL for a handful of newly onboarded SKUs. Staging only FLAGS
  that; imputation is business logic and belongs in intermediate.

  is_defect_sku is not selected: it is a generator artifact. The analysis has to
  find the problem SKUs from their return behavior, not from a label.
#}
select
    product_key,
    sku,
    trim(product_name)                                  as product_name,
    category,
    list_price::numeric(10,2)                           as list_price,
    unit_cost::numeric(10,2)                            as unit_cost,
    (unit_cost is null)                                 as unit_cost_missing,
    weight_lbs::numeric(6,2)                            as weight_lbs,
    {{ parse_mixed_date('valid_from') }}                as valid_from,
    coalesce({{ parse_mixed_date('valid_to') }}, date '9999-12-31') as valid_to,
    is_current::boolean                                 as is_current
from {{ source('raw', 'raw_products') }}
