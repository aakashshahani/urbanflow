-- Weather dimension at hourly grain, deduped to one row per hour. Joined to the
-- fact on the trip's pickup hour for demand-versus-weather analysis.
with hourly as (
    select
        date_trunc('hour', cast(date_parse(observed_at, '%Y-%m-%dT%H:%i') as timestamp(6))) as weather_hour,
        avg(temperature_2m) as temperature_2m,
        avg(precipitation)  as precipitation,
        avg(wind_speed_10m) as wind_speed_10m
    from {{ source('bronze', 'weather_hourly') }}
    group by 1
)

select
    cast(date_format(weather_hour, '%Y%m%d%H') as bigint) as weather_key,
    weather_hour,
    temperature_2m,
    precipitation,
    wind_speed_10m,
    precipitation > 0 as is_wet
from hourly
