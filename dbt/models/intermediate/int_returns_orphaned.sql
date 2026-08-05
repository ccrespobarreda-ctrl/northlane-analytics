{#
  Returns that do NOT resolve to an order line -- either the foreign key is
  null, or it points at a line that does not exist.

  These are quarantined, not deleted. Dropping them would understate refunds
  and quietly improve margin; the dollar value is reported in
  docs/data_quality_report.md so a reader can judge the exposure.

  Root cause in the source system: returns processed through a channel that
  does not write back the originating line reference.
#}
select
    r.return_id,
    r.order_line_key,
    r.order_id,
    r.sku,
    r.return_date,
    r.original_order_date,
    r.quantity_returned,
    r.refund_amount,
    r.return_shipping_cost,
    r.return_reason,
    case
        when r.order_line_key is null then 'missing_foreign_key'
        else 'foreign_key_not_found'
    end                                                 as orphan_reason
from {{ ref('stg_returns') }} r
left join {{ ref('int_order_lines_enriched') }} l
    on l.order_line_key = r.order_line_key
where l.order_line_key is null
