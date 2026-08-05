{#
  The source system emits three date formats in a single text column:
    2025-01-15   (ISO)
    01/15/2025   (US)
    15-Jan-2025  (abbreviated month)

  to_date() would raise on the first mismatch, so we branch on the shape of the
  string. Anything that matches none of the three returns NULL and is caught by
  the not_null test on the staging model -- silence is not an option.
#}
{% macro parse_mixed_date(col) %}
case
    when {{ col }} ~ '^\d{4}-\d{2}-\d{2}'
        then to_date(substring({{ col }} from 1 for 10), 'YYYY-MM-DD')
    when {{ col }} ~ '^\d{2}/\d{2}/\d{4}$'
        then to_date({{ col }}, 'MM/DD/YYYY')
    when {{ col }} ~ '^\d{1,2}-[A-Za-z]{3}-\d{4}$'
        then to_date({{ col }}, 'DD-Mon-YYYY')
end
{% endmacro %}
