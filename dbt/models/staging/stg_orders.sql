{#
  Order header. Pure casting and string cleaning -- no joins, no dedupe.
  state_code arrives as 'CA', 'California' or 'ca.'; here it is only
  normalized as text. Resolving full names to two-letter codes needs a lookup,
  which happens in int_orders_conformed.

  sales_tax is carried through but is NOT revenue: it is money collected on
  behalf of the state. See docs/business_rules.md.
#}
select
    order_id,
    customer_key,
    order_seq::int                                      as order_seq,
    {{ parse_mixed_date('order_date') }}                as order_date,
    is_first_order::boolean                             as is_first_order_reported,
    {{ clean_state_text('state_code') }}                as state_text,
    acquisition_channel,
    sales_channel,
    shipping_zone::int                                  as shipping_zone,
    order_gross_revenue::numeric(12,2)                  as order_gross_revenue,
    order_net_revenue::numeric(12,2)                    as order_net_revenue,
    order_units::int                                    as order_units,
    order_weight::numeric(8,2)                          as order_billable_weight_lbs,
    shipping_revenue::numeric(10,2)                     as shipping_revenue,
    shipping_cost::numeric(10,2)                        as shipping_cost,
    sales_tax::numeric(10,2)                            as sales_tax,
    payment_fee::numeric(10,2)                          as payment_fee,
    pick_pack_cost::numeric(10,2)                       as pick_pack_cost
from {{ source('raw', 'raw_orders') }}
