-- The sum of line net revenue must equal the order header total.
--
-- This is the single most valuable integrity test in the project. It catches
-- both directions of failure at once: a fan-out in the SCD2 or returns join
-- (lines sum too high) and dropped lines from a bad inner join (too low).
-- Tolerance is 1 cent per line to absorb the allocation rounding.
with lines as (
    select
        order_id,
        count(*)                as line_count,
        sum(discounted_revenue) as lines_net_revenue
    from {{ ref('fct_order_lines') }}
    group by order_id
)

select
    o.order_id,
    o.order_net_revenue        as header_net_revenue,
    l.lines_net_revenue,
    l.line_count,
    abs(o.order_net_revenue - l.lines_net_revenue) as variance
from {{ ref('int_orders_conformed') }} o
join lines l on l.order_id = o.order_id
where abs(o.order_net_revenue - l.lines_net_revenue) > 0.01 * l.line_count
