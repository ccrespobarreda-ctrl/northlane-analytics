{#
  State arrives as 'CA', 'California' or 'ca.'. This strips punctuation and
  case; resolving full names to codes needs a lookup, done in stg_orders
  against stg_geography.
#}
{% macro clean_state_text(col) %}
    upper(trim(replace({{ col }}, '.', '')))
{% endmacro %}


{#
  Surrogate key without a dbt_utils dependency. concat_ws skips NULLs, which
  would let ('a', null, 'b') and ('a', 'b') collide, so NULLs are coalesced to
  a sentinel first.
#}
{% macro surrogate_key(cols) %}
    md5(concat_ws('|'
    {%- for c in cols %}
        , coalesce(cast({{ c }} as text), '~')
    {%- endfor %}
    ))
{% endmacro %}
