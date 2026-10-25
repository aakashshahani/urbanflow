-- Gold marketplace metric: trips, revenue, and average distance per pickup zone
-- per hour, joined to that hour's weather. This is the table the pricing/supply
-- question lands on and what the FastAPI /metrics endpoint reads.
-- Built from the gold layer (fact_trips + dim_weather), not silver, so its counts
-- match the fact table: exact-duplicate trips and trips ending before they start
-- are already removed there.
with trips as (
    select
        pickup_zone_id,
        date_trunc('hour', pickup_ts) as pickup_hour,
        pickup_weather_key,
        count(*)                      as trip_count,
        sum(total_amount)             as revenue,
        avg(trip_distance)            as avg_distance
    from {{ ref('fact_trips') }}
    group by 1, 2, 3
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
left join {{ ref('dim_weather') }} w
    on t.pickup_weather_key = w.weather_key
