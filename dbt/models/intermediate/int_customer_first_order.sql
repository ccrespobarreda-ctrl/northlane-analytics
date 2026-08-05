{#
  First order derived from observed orders, not taken from the customer record.

  The source customer table carries first_order_date, but that field is only as
  good as the source system's own hygiene, and it is computed BEFORE
  deduplication. Deriving it from conformed orders means the cohort assignment
  and the is_first_order flag agree with the fact table by construction.

  acquisition_channel is frozen at the first order. Every cohort and LTV number
  downstream depends on it never being reassigned.
#}
with ranked as (
    select
        customer_key,
        order_id,
        order_date,
        acquisition_channel,
        state_code,
        row_number() over (partition by customer_key order by order_date, order_id)
            as order_rank,
        count(*) over (partition by customer_key)        as lifetime_orders
    from {{ ref('int_orders_conformed') }}
)

select
    customer_key,
    order_id                                            as first_order_id,
    order_date                                          as first_order_date,
    date_trunc('month', order_date)::date               as cohort_month,
    acquisition_channel,
    state_code                                          as first_order_state_code,
    lifetime_orders
from ranked
where order_rank = 1
