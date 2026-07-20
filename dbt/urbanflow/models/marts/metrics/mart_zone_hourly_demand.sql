-- Gold marketplace metric: trips, revenue, and average distance per pickup zone
-- per hour, joined to that hour's weather. This is the table the pricing/supply
-- question lands on and what the FastAPI /metrics endpoint reads.
with trips as (
    select
        pickup_zone_id,
        date_trunc('hour', pickup_ts) as pickup_hour,
        count(*)                      as trip_count,
        sum(total_amount)             as revenue,
        avg(trip_distance)            as avg_distance
    from {{ ref('stg_yellow_trips') }}
    group by 1, 2
),

weather as (
    select
        date_trunc('hour', cast(date_parse(observed_at, '%Y-%m-%dT%H:%i') as timestamp(6))) as weather_hour,
        avg(temperature_2m) as temperature_2m,
        avg(precipitation)  as precipitation
    from {{ source('bronze', 'weather_hourly') }}
    group by 1
)

select
    t.pickup_zone_id,
    t.pickup_hour,
    t.trip_count,
    t.revenue,
    t.avg_distance,
    w.temperature_2m,
    w.precipitation
from trips t
left join weather w
    on t.pickup_hour = w.weather_hour
