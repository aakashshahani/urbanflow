-- Central fact at one row per trip, with foreign keys to the conformed dimensions.
-- Incremental so daily runs and backfills only process new pickup days; the Iceberg
-- MERGE keeps re-runs idempotent (no duplicate trips on replay).
{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='trip_key',
        table_type='iceberg',
    )
}}
with trips as (
    select * from {{ ref('stg_yellow_trips') }}
    {% if is_incremental() %}
    where cast(pickup_ts as date) > (select coalesce(max(pickup_date), date '1900-01-01') from {{ this }})
    {% endif %}
)

select
    -- deterministic natural key so a replayed row merges instead of duplicating
    to_hex(md5(to_utf8(
        cast(pickup_ts as varchar) || '|' ||
        cast(pickup_zone_id as varchar) || '|' ||
        cast(dropoff_zone_id as varchar) || '|' ||
        cast(total_amount as varchar)
    )))                                              as trip_key,
    cast(pickup_ts as date)                          as pickup_date,
    cast(date_format(pickup_ts, '%Y%m%d') as integer) as pickup_date_key,
    cast(date_format(pickup_ts, '%Y%m%d%H') as bigint) as pickup_weather_key,
    pickup_zone_id,
    dropoff_zone_id,
    pickup_ts,
    dropoff_ts,
    date_diff('minute', pickup_ts, dropoff_ts)       as trip_minutes,
    passenger_count,
    trip_distance,
    total_amount
from trips
where dropoff_ts >= pickup_ts
