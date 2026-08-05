select
    {{ parse_mixed_date('date') }}                      as spend_date,
    channel                                             as channel_name,
    campaign_id,
    campaign_objective,
    spend::numeric(12,2)                                as spend,
    impressions::bigint                                 as impressions,
    clicks::int                                         as clicks,
    platform_reported_conversions::int                  as platform_reported_conversions,
    platform_reported_revenue::numeric(14,2)            as platform_reported_revenue
from {{ source('raw', 'raw_ad_spend') }}
