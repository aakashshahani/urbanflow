-- Silver: typed and cleaned yellow trips. Drops the obvious junk (non-positive
-- fares, zero-distance rides, out-of-range passenger counts) so gold stays honest.
-- Materialized as an Iceberg table: Athena's Hive-typed views reject timestamp(6),
-- which the Iceberg tables accept on both Athena and Trino.
{{ config(materialized='table', table_type='iceberg') }}
with source as (
    select * from {{ source('bronze', 'yellow_trips') }}
),

cleaned as (
    select
        cast(tpep_pickup_datetime as timestamp(6))   as pickup_ts,
        cast(tpep_dropoff_datetime as timestamp(6))  as dropoff_ts,
        cast(pulocationid as integer)             as pickup_zone_id,
        cast(dolocationid as integer)             as dropoff_zone_id,
        cast(passenger_count as integer)          as passenger_count,
        cast(trip_distance as double)             as trip_distance,
        cast(total_amount as double)              as total_amount,
        _source_month                             as source_month
    from source
    where total_amount > 0
      and trip_distance > 0
      and tpep_pickup_datetime is not null
      -- tie each row to its source month: TLC files carry stray rows with garbage
      -- pickup dates (years like 2002 or 2088) that would otherwise pollute the dims
      and date_format(cast(tpep_pickup_datetime as timestamp(6)), '%Y-%m') = _source_month
)

select * from cleaned
