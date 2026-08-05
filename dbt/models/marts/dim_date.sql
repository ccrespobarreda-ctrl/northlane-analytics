{#
  Date spine generated in SQL rather than sourced, so every calendar day exists
  even if nothing was sold. Without a dense spine, "revenue by day" charts
  silently skip zero days and time-intelligence measures in Power BI break.

  Thanksgiving is computed as the fourth Thursday in November, then BFCM is the
  four days following it. Hard-coding those dates per year is how a dashboard
  starts lying in January.
#}
with spine as (
    select generate_series(
        date '2023-01-01',
        date '2025-12-31',
        interval '1 day'
    )::date as date_day
),

thanksgiving as (
    select
        extract(year from date_day)::int                 as cal_year,
        date_day                                         as thanksgiving_date
    from (
        select
            date_day,
            row_number() over (
                partition by extract(year from date_day)
                order by date_day
            ) as thursday_rank
        from spine
        where extract(month from date_day) = 11
          and extract(isodow from date_day) = 4
    ) t
    where thursday_rank = 4
)

select
    to_char(s.date_day, 'YYYYMMDD')::int                 as date_key,
    s.date_day,
    extract(year from s.date_day)::int                   as cal_year,
    extract(quarter from s.date_day)::int                as cal_quarter,
    extract(month from s.date_day)::int                  as cal_month,
    to_char(s.date_day, 'Mon')                           as month_name,
    date_trunc('month', s.date_day)::date                as month_start,
    to_char(s.date_day, 'YYYY-MM')                       as year_month,
    extract(day from s.date_day)::int                    as day_of_month,
    extract(isodow from s.date_day)::int                  as iso_day_of_week,
    to_char(s.date_day, 'Dy')                            as day_name,
    (extract(isodow from s.date_day) in (6, 7))          as is_weekend,
    (extract(month from s.date_day) in (10, 11, 12))     as is_holiday_season,
    (s.date_day between t.thanksgiving_date + 1
                    and t.thanksgiving_date + 4)         as is_bfcm
from spine s
left join thanksgiving t on t.cal_year = extract(year from s.date_day)
