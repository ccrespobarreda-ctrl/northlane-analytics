-- The revenue waterfall must close at every step:
--     discounted_revenue = gross_revenue - discount
--     net_revenue        = discounted_revenue - refunds
--
-- This is the guard on the decimal-point typo correction. If the fix were
-- applied to the wrong column, or applied twice, these identities break even
-- though every individual value still looks plausible.
select
    order_line_key,
    gross_revenue,
    discount,
    discounted_revenue,
    refund_amount,
    net_revenue,
    'discounted_revenue <> gross - discount' as failed_identity
from {{ ref('fct_order_lines') }}
where abs(gross_revenue - discount - discounted_revenue) > 0.01

union all

select
    order_line_key,
    gross_revenue,
    discount,
    discounted_revenue,
    refund_amount,
    net_revenue,
    'net_revenue <> discounted - refunds'
from {{ ref('fct_order_lines') }}
where abs(discounted_revenue - refund_amount - net_revenue) > 0.01
