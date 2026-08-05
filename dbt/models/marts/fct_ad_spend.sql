{#
  Grain: date x channel x campaign.

  platform_reported_revenue is kept deliberately alongside spend so the
  dashboard can show the gap against real order revenue. Platforms over-credit
  themselves through overlapping attribution windows; presenting only their
  numbers imports their bias into the P&L.
#}
select
    {{ surrogate_key(['spend_date', 'channel_name', 'campaign_id']) }}
                                                        as ad_spend_key,
    to_char(spend_date, 'YYYYMMDD')::int                as date_key,
    spend_date,
    channel_name                                        as channel_key,
    campaign_id,
    campaign_objective,
    spend,
    impressions,
    clicks,
    platform_reported_conversions,
    platform_reported_revenue,
    case when impressions > 0
         then round(spend / impressions * 1000, 2) end   as cpm,
    case when clicks > 0
         then round(spend / clicks, 2) end               as cpc,
    case when spend > 0
         then round(platform_reported_revenue / spend, 3) end
                                                        as platform_roas
from {{ ref('stg_ad_spend') }}
