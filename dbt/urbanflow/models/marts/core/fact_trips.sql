-- Central fact at one row per trip, with foreign keys to the conformed dimensions.
-- Incremental so daily runs and backfills only process new pickup days; the Iceberg
-- MERGE keeps re-runs idempotent (no duplicate trips on replay).
{# Iceberg day-partitioning, expressed per adapter: Athena uses partitioned_by,
   Trino uses the iceberg partitioning table property. Both prune a single-day scan. #}
{% if target.type == 'athena' %}
{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='trip_key',
        table_type='iceberg',
        partitioned_by=["day(pickup_ts)"],
    )
}}
{% else %}
{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='trip_key',
        table_type='iceberg',
        properties={'partitioning': "ARRAY['day(pickup_ts)']"},
    )
}}
{% endif %}
with trips as (
    select * from {{ ref('stg_yellow_trips') }}
    {% if is_incremental() %}
    where cast(pickup_ts as date) > (select coalesce(max(pickup_date), date '1900-01-01') from {{ this }})
    {% endif %}
),

keyed as (
    select
        -- deterministic natural key over the full trip attributes so a replayed row
        -- merges instead of duplicating (idempotent backfills)
        -- coalesce nullable parts: real TLC rows carry null passenger_count and
        -- dropoff zone, and concatenating a null in Trino yields a null key
        to_hex(md5(to_utf8(
            cast(pickup_ts as varchar) || '|' ||
            cast(dropoff_ts as varchar) || '|' ||
            cast(pickup_zone_id as varchar) || '|' ||
            coalesce(cast(dropoff_zone_id as varchar), '') || '|' ||
            cast(trip_distance as varchar) || '|' ||
            cast(total_amount as varchar) || '|' ||
            coalesce(cast(passenger_count as varchar), '')
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
),

-- collapse exact-duplicate trip records (same time, zones, distance, fare, riders)
-- to one row so trip_key is unique and the merge grain is one row per trip.
-- Done with a windowed subquery rather than QUALIFY, which Trino and Athena lack.
ranked as (
    select
        keyed.*,
        row_number() over (partition by trip_key order by dropoff_ts) as _rn
    from keyed
)

select
    trip_key,
    pickup_date,
    pickup_date_key,
    pickup_weather_key,
    pickup_zone_id,
    dropoff_zone_id,
    pickup_ts,
    dropoff_ts,
    trip_minutes,
    passenger_count,
    trip_distance,
    total_amount
from ranked
where _rn = 1
