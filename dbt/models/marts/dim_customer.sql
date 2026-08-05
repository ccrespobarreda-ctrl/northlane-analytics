{#
  Grain: one row per customer. first_order_date and acquisition_channel are
  derived from conformed orders, not copied from the source record, so cohort
  membership always agrees with the fact table.
#}
select
    f.customer_key,
    c.email_hash,
    f.first_order_date,
    f.cohort_month,
    f.acquisition_channel                               as acquisition_channel_key,
    coalesce(g.state_code, f.first_order_state_code)     as home_geography_key,
    f.lifetime_orders,
    (f.lifetime_orders > 1)                             as is_repeat_customer,
    -- Cohorts younger than 12 months cannot be compared on 12-month LTV.
    (f.first_order_date <= date '2025-12-31' - interval '365 days')
                                                        as has_complete_12m_window
from {{ ref('int_customer_first_order') }} f
left join {{ ref('stg_customers') }} c using (customer_key)
left join {{ ref('stg_geography') }} g
    on g.state_code = f.first_order_state_code
