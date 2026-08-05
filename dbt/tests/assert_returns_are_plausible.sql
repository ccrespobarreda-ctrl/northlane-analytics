-- Returns cannot precede the sale, cannot exceed the units sold, and cannot
-- arrive after the 60-day policy window.
select
    order_line_key,
    quantity,
    units_returned,
    order_date
from {{ ref('fct_order_lines') }}
where units_returned > quantity

union all

select
    f.order_line_key,
    null::int,
    f.quantity_returned,
    f.original_order_date
from {{ ref('fct_returns') }} f
where f.days_to_return < 0
   or f.days_to_return > 60
