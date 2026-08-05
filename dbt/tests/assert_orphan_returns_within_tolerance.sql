{{ config(severity = 'warn', warn_if = '>0') }}
-- Orphaned returns are a known source defect, quarantined rather than dropped.
-- This does not fail the build, but it warns if the share ever exceeds 2% of
-- refund value -- at which point the quarantine stops being a rounding error
-- and starts being a material misstatement of margin.
with orphaned as (
    select coalesce(sum(refund_amount), 0) as amt
    from {{ ref('int_returns_orphaned') }}
),
matched as (
    select coalesce(sum(refund_amount), 0) as amt
    from {{ ref('fct_order_lines') }}
)
select
    o.amt                                   as orphaned_refunds,
    m.amt                                   as matched_refunds,
    round(o.amt / nullif(o.amt + m.amt, 0), 4) as orphan_share
from orphaned o cross join matched m
where o.amt / nullif(o.amt + m.amt, 0) > 0.02
