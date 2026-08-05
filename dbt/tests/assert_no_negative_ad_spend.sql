select ad_spend_key, spend
from {{ ref('fct_ad_spend') }}
where spend < 0
