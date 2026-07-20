-- Date dimension spanning the loaded trips. Built with a sequence spine so it needs
-- no external package and compiles the same on Trino and Athena.
with bounds as (
    select
        cast(min(pickup_ts) as date) as start_day,
        cast(max(pickup_ts) as date) as end_day
    from {{ ref('stg_yellow_trips') }}
),

spine as (
    select d as date_day
    from bounds
    cross join unnest(sequence(bounds.start_day, bounds.end_day, interval '1' day)) as t (d)
)

select
    cast(date_format(date_day, '%Y%m%d') as integer) as date_key,
    date_day,
    year(date_day)                                   as year,
    month(date_day)                                  as month,
    day(date_day)                                    as day_of_month,
    day_of_week(date_day)                            as day_of_week,
    day_of_week(date_day) in (6, 7)                  as is_weekend
from spine
