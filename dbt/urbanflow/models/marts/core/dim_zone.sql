-- Conformed zone dimension with SCD2 history from the snapshot. is_current flags
-- the live version; downstream facts join on the current row by default.
select
    zone_id,
    borough,
    zone_name,
    service_zone,
    dbt_valid_from                as valid_from,
    dbt_valid_to                  as valid_to,
    dbt_valid_to is null          as is_current
from {{ ref('zone_snapshot') }}
