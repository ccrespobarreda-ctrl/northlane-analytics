{#
  Columns deliberately NOT selected: repeat_propensity, discount_affinity,
  return_uplift. Those are latent behavioral parameters from the data
  generator. They are not observable in a real business and using them would
  be target leakage -- any "insight" derived from them would be circular.
  They are dropped here so no downstream model can reach them.
#}
select
    customer_key,
    lower(trim(email))                                  as email,
    md5(lower(trim(email)))                             as email_hash,
    trim(first_name)                                    as first_name,
    trim(last_name)                                     as last_name,
    {{ clean_state_text('state_code') }}                as state_code_raw,
    acquisition_channel,
    {{ parse_mixed_date('first_order_date') }}          as reported_first_order_date
from {{ source('raw', 'raw_customers') }}
