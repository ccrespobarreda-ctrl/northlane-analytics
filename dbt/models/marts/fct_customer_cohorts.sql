{#
  Cohort retention and contribution-based LTV.
  Grain: cohort month x acquisition channel x months since first order.

  Two decisions that most cohort analyses get wrong:

  1. LTV is measured in CM2, not revenue. Revenue LTV is a vanity metric: it
     ignores that the second order might have been shipped free to Zone 8 and
     half returned.

  2. months_since_first is derived from calendar month difference, and
     is_complete_window marks whether the cohort has actually LIVED that long.
     Plotting an incomplete cohort on a 12-month LTV curve makes recent cohorts
     look like they are collapsing when they are simply young.
#}
with orders as (
    select
        l.customer_key,
        l.order_id,
        l.order_date,
        sum(l.net_revenue)                              as net_revenue,
        sum(l.cm2)                                      as cm2
    from {{ ref('fct_order_lines') }} l
    group by 1, 2, 3
),

with_cohort as (
    select
        o.*,
        d.cohort_month,
        d.acquisition_channel_key,
        (((extract(year from o.order_date) - extract(year from d.cohort_month)) * 12
          + (extract(month from o.order_date) - extract(month from d.cohort_month))
         ))::int                                        as months_since_first
    from orders o
    inner join {{ ref('dim_customer') }} d using (customer_key)
),

cohort_size as (
    select
        cohort_month,
        acquisition_channel_key,
        count(*)                                        as cohort_customers
    from {{ ref('dim_customer') }}
    group by 1, 2
)

select
    w.cohort_month,
    w.acquisition_channel_key,
    w.months_since_first,
    cs.cohort_customers,

    count(distinct w.customer_key)                      as active_customers,
    count(*)                                            as orders,
    sum(w.net_revenue)                                  as net_revenue,
    sum(w.cm2)                                          as cm2,

    round(count(distinct w.customer_key)::numeric
          / nullif(cs.cohort_customers, 0), 4)          as retention_rate,
    round(sum(w.cm2) / nullif(cs.cohort_customers, 0), 2)
                                                        as cm2_per_cohort_customer,

    -- Has this cohort actually had time to reach this month yet?
    (w.cohort_month + (w.months_since_first || ' months')::interval
        <= date '2025-12-31')                           as is_complete_window

from with_cohort w
inner join cohort_size cs
    on cs.cohort_month = w.cohort_month
   and cs.acquisition_channel_key = w.acquisition_channel_key
where w.months_since_first between 0 and 23
group by
    w.cohort_month,
    w.acquisition_channel_key,
    w.months_since_first,
    cs.cohort_customers
