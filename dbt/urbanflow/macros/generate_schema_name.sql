{#
  Use the model's configured +schema (silver, gold, snapshots) as the real schema
  name instead of dbt's default target-prefixed form, so the lakehouse namespaces
  read cleanly in Trino and Athena.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
