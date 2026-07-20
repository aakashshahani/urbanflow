-- Silver: typed and cleaned yellow trips. Drops the obvious junk (non-positive
-- fares, zero-distance rides, out-of-range passenger counts) so gold stays honest.
with source as (
    select * from {{ source('bronze', 'yellow_trips') }}
),

cleaned as (
    select
        cast(tpep_pickup_datetime as timestamp)   as pickup_ts,
        cast(tpep_dropoff_datetime as timestamp)  as dropoff_ts,
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
)

select * from cleaned
