{% snapshot zone_snapshot %}
{{
    config(
        target_schema='snapshots',
        unique_key='zone_id',
        strategy='check',
        check_cols=['borough', 'zone_name', 'service_zone'],
        invalidate_hard_deletes=True,
    )
}}
-- SCD Type 2 over the taxi-zone lookup. Zones get renamed and reclassified over
-- time; the check strategy opens a new version whenever borough, name, or service
-- zone changes, so dim_zone keeps full history with valid_from / valid_to.
select
    cast("LocationID" as integer) as zone_id,
    "Borough"                     as borough,
    "Zone"                        as zone_name,
    service_zone
from {{ ref('taxi_zone_lookup') }}
{% endsnapshot %}
