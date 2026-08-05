{#
  Channel type is not cosmetic. It determines whether spend belongs in CM3:
  paid acquisition is a variable cost of getting a customer, owned channels are
  largely fixed, and retargeting spends against demand that already exists.
  Mixing them produces a blended ROAS that cannot inform any decision.
#}
with channels as (
    select distinct acquisition_channel as channel_name
    from {{ ref('int_orders_conformed') }}
    where acquisition_channel is not null
)

select
    channel_name                                        as channel_key,
    channel_name,
    case
        when channel_name in ('Google Search', 'Meta Prospecting', 'TikTok Ads')
            then 'Paid Prospecting'
        when channel_name = 'Meta Retargeting' then 'Paid Retargeting'
        when channel_name = 'Affiliate'        then 'Affiliate'
        else 'Owned'
    end                                                 as channel_type,
    (channel_name in ('Google Search', 'Meta Prospecting',
                      'TikTok Ads', 'Affiliate'))       as is_paid_acquisition,
    (channel_name in ('Google Search', 'Meta Prospecting',
                      'TikTok Ads', 'Meta Retargeting',
                      'Affiliate'))                     as is_variable_cost
from channels
