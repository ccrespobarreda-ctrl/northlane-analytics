{#
  Aggregated contribution for dashboard performance. Grain:
  date x acquisition channel x state x category.

  Deliberately stops at CM2. CM3 requires ad spend, and ad spend cannot be
  attributed to a state or a category -- the platforms simply do not report it
  at that grain. Any state-level CM3 would be an allocation dressed up as a
  measurement, so CM3 lives only at channel grain in
  fct_channel_economics_monthly.
#}
select
    order_date_key,
    order_date,
    acquisition_channel_key,
    geography_key,
    category,
    sales_channel,

    count(distinct order_id)                            as orders,
    sum(quantity)                                       as units,
    sum(units_returned)                                 as units_returned,

    sum(gross_revenue)                                  as gross_revenue,
    sum(discount)                                       as discount,
    sum(discounted_revenue)                             as discounted_revenue,
    sum(refund_amount)                                  as refunds,
    sum(net_revenue)                                    as net_revenue,

    sum(cogs)                                           as cogs,
    sum(cogs_recovered)                                 as cogs_recovered,
    sum(shipping_revenue)                               as shipping_revenue,
    sum(shipping_cost)                                  as shipping_cost,
    sum(payment_fee)                                    as payment_fee,
    sum(pick_pack_cost)                                 as pick_pack_cost,
    sum(return_shipping_cost)                           as return_shipping_cost,
    sum(restock_labor_cost)                            as restock_labor_cost,

    sum(cm1)                                            as cm1,
    sum(cm2)                                            as cm2
from {{ ref('fct_order_lines') }}
group by 1, 2, 3, 4, 5, 6
