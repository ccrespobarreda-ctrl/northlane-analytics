-- Reference data: clean on arrival, but still typed explicitly.
select
    state_code                                          as state_code,
    state_name,
    census_region,
    census_division,
    shipping_zone::int                                  as shipping_zone,
    population_millions::numeric(6,2)                   as population_millions,
    has_state_sales_tax::boolean                        as has_state_sales_tax,
    nexus_threshold_usd::numeric(12,2)                  as nexus_threshold_usd
from {{ source('raw', 'raw_geography') }}
