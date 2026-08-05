{#
  The most consequential model in the project. Three corrections happen here,
  each of which changes reported margin.

  1. SCD2 RANGE JOIN
     Unit cost is joined on the version valid on the ORDER DATE:
         on p.sku = l.sku and l.order_date between p.valid_from and p.valid_to
     Joining on the current version instead would apply 2025 supplier pricing to
     2023 orders and quietly rewrite two years of margin history. The range join
     is why valid_to was coerced to 9999-12-31 in staging.

  2. DECIMAL-POINT TYPO
     A small number of lines carry a price 10x the product's list price -- a
     data-entry error in the price feed. Detected by comparing against
     list_price (which is why this cannot live in staging: it needs a join) and
     corrected by dividing by ten. Only gross revenue was corrupted upstream;
     discount and net were not, so after correcting gross the identity
     net = gross - discount holds again, and a test asserts it.

  3. COGS RECOMPUTED, NOT TRUSTED
     line_cogs from the source is a snapshot that can disagree with the
     dimension. COGS is recomputed as quantity * SCD2 unit cost, and the
     disagreement is retained as cogs_variance so the data quality report can
     quantify it rather than assert the two agree.

  Order lines belonging to deduplicated orders disappear here via the inner
  join to int_orders_conformed. That is intentional: one source of truth for
  which orders exist.
#}

with lines as (
    select * from {{ ref('stg_order_lines') }}
),

orders as (
    select * from {{ ref('int_orders_conformed') }}
),

products as (
    select * from {{ ref('int_products_costed') }}
),

joined as (
    select
        l.order_line_key,
        l.order_id,
        l.line_number,
        l.customer_key,
        o.order_date,
        o.state_code,
        o.acquisition_channel,
        o.sales_channel,
        o.shipping_zone,
        l.sku,
        p.product_key,
        p.product_name,
        p.category,
        p.list_price,
        p.unit_cost,
        p.unit_cost_is_imputed,
        l.quantity,
        l.unit_price_gross_source,
        l.line_gross_revenue_source,
        l.line_discount_source,
        l.line_net_revenue_source,
        l.line_cogs_source,
        l.discount_code,
        l.billable_weight_lbs,
        l.shipping_revenue_alloc,
        l.shipping_cost_alloc,
        l.payment_fee_alloc,
        l.pick_pack_alloc,

        -- Typo detection: a real price is never triple its own list price.
        (l.unit_price_gross_source > p.list_price * 3)   as price_looks_corrupted

    from lines l
    inner join orders o
        on o.order_id = l.order_id
    inner join products p
        on p.sku = l.sku
       and o.order_date between p.valid_from and p.valid_to
),

corrected as (
    select
        *,
        case when price_looks_corrupted
             then round(unit_price_gross_source / 10, 2)
             else unit_price_gross_source
        end                                             as unit_price_gross,
        case when price_looks_corrupted
             then round(line_gross_revenue_source / 10, 2)
             else line_gross_revenue_source
        end                                             as line_gross_revenue
    from joined
)

select
    order_line_key,
    order_id,
    line_number,
    customer_key,
    order_date,
    state_code,
    acquisition_channel,
    sales_channel,
    shipping_zone,
    sku,
    product_key,
    product_name,
    category,
    list_price,
    unit_cost,
    unit_cost_is_imputed,
    quantity,

    unit_price_gross,
    line_gross_revenue,
    line_discount_source                                as line_discount,
    line_gross_revenue - line_discount_source           as line_net_revenue,

    -- COGS from the dimension, not from the source snapshot
    round(unit_cost * quantity, 2)                      as line_cogs,
    line_cogs_source,
    round(unit_cost * quantity, 2) - line_cogs_source   as cogs_variance,

    discount_code,
    case when line_gross_revenue > 0
         then round(line_discount_source / line_gross_revenue, 4)
         else 0
    end                                                 as discount_rate,

    billable_weight_lbs,
    shipping_revenue_alloc,
    shipping_cost_alloc,
    payment_fee_alloc,
    pick_pack_alloc,
    price_looks_corrupted                               as price_was_corrected

from corrected
