{#
  The only model where CM3 is computed, because it is the only grain at which ad
  spend is actually measured. Grain: month x acquisition channel.

  Spend is joined on the CHANNEL the customer was acquired through, which means
  a repeat purchase from a Google-acquired customer credits Google. That is the
  correct treatment for judging acquisition quality and the wrong treatment for
  judging this month's media buy -- stated here so the distinction is explicit
  rather than assumed.
#}
with revenue as (
    select
        date_trunc('month', order_date)::date            as month_start,
        acquisition_channel_key,
        count(distinct order_id)                         as orders,
        count(distinct customer_key)                     as active_customers,
        sum(net_revenue)                                 as net_revenue,
        sum(cm1)                                         as cm1,
        sum(cm2)                                         as cm2
    from {{ ref('fct_order_lines') }}
    group by 1, 2
),

spend as (
    select
        date_trunc('month', spend_date)::date            as month_start,
        channel_key                                      as acquisition_channel_key,
        sum(spend)                                       as spend,
        sum(platform_reported_revenue)                   as platform_reported_revenue,
        sum(platform_reported_conversions)               as platform_reported_conversions
    from {{ ref('fct_ad_spend') }}
    group by 1, 2
),

new_customers as (
    select
        cohort_month                                     as month_start,
        acquisition_channel_key,
        count(*)                                         as new_customers
    from {{ ref('dim_customer') }}
    group by 1, 2
)

select
    coalesce(r.month_start, s.month_start)               as month_start,
    coalesce(r.acquisition_channel_key, s.acquisition_channel_key)
                                                        as acquisition_channel_key,
    c.channel_type,
    c.is_paid_acquisition,

    coalesce(r.orders, 0)                               as orders,
    coalesce(r.active_customers, 0)                     as active_customers,
    coalesce(n.new_customers, 0)                        as new_customers,

    coalesce(r.net_revenue, 0)                          as net_revenue,
    coalesce(r.cm1, 0)                                  as cm1,
    coalesce(r.cm2, 0)                                  as cm2,
    coalesce(s.spend, 0)                                as ad_spend,
    coalesce(r.cm2, 0) - coalesce(s.spend, 0)           as cm3,

    coalesce(s.platform_reported_revenue, 0)            as platform_reported_revenue,

    -- Ratios. Every denominator is guarded: a zero-spend month must not turn
    -- the whole column into an error or an infinity.
    case when coalesce(s.spend, 0) > 0
         then round(coalesce(r.net_revenue, 0) / s.spend, 3) end   as mer,
    case when coalesce(s.spend, 0) > 0
         then round(coalesce(s.platform_reported_revenue, 0) / s.spend, 3) end
                                                        as platform_roas,
    case when coalesce(n.new_customers, 0) > 0
         then round(coalesce(s.spend, 0) / n.new_customers, 2) end as ncac,
    case when coalesce(r.net_revenue, 0) > 0
         then round((coalesce(r.cm2, 0) - coalesce(s.spend, 0))
                    / r.net_revenue, 4) end             as cm3_margin_pct

from revenue r
full outer join spend s
    on s.month_start = r.month_start
   and s.acquisition_channel_key = r.acquisition_channel_key
left join new_customers n
    on n.month_start = coalesce(r.month_start, s.month_start)
   and n.acquisition_channel_key = coalesce(r.acquisition_channel_key,
                                            s.acquisition_channel_key)
left join {{ ref('dim_channel') }} c
    on c.channel_key = coalesce(r.acquisition_channel_key, s.acquisition_channel_key)
