{#
  shipping_zone is the economically meaningful attribute here: it is the
  distance band from the Columbus, OH fulfillment center and it drives the
  carrier invoice. A geography dimension without it produces maps that show
  where customers live rather than where money is made.

  nexus columns are business modeling attributes only -- see
  docs/business_rules.md. Nothing here constitutes tax advice.
#}
select
    state_code                                          as geography_key,
    state_code,
    state_name,
    census_region,
    census_division,
    shipping_zone,
    case
        when shipping_zone <= 3 then 'Near (Z2-Z3)'
        when shipping_zone <= 5 then 'Mid (Z4-Z5)'
        else 'Far (Z6-Z8)'
    end                                                 as shipping_zone_band,
    population_millions,
    has_state_sales_tax,
    nexus_threshold_usd
from {{ ref('stg_geography') }}
