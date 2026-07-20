"""Great Expectations suite for bronze yellow trips.

Runs against an in-memory dataframe through an ephemeral GX context, so it needs no
persisted GX project on disk and can gate the pipeline from inside the Airflow task.
`validate_df` returns the raw result; `assert_valid` raises so the DAG fails on a bad load.
"""
from __future__ import annotations

import great_expectations as gx
from great_expectations import expectations as gxe

SUITE_NAME = "bronze_yellow_trips"


def build_suite() -> gx.ExpectationSuite:
    # Bronze is raw. This gate checks that data arrived, keys are present, and values
    # are not corrupt. Business rules (positive fare, non-zero distance) are enforced
    # downstream by the silver filter and dbt tests, so a real load with the usual
    # refunds and zero-distance trips is not wrongly rejected here. `mostly` tolerates
    # the rare outlier while still catching a genuinely broken load.
    suite = gx.ExpectationSuite(name=SUITE_NAME)
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=1))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="tpep_pickup_datetime"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="pulocationid"))
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="total_amount", min_value=-1000, max_value=100000, mostly=0.99
        )
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="trip_distance", min_value=0, max_value=1000, mostly=0.99
        )
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="passenger_count", min_value=0, max_value=9, mostly=0.95
        )
    )
    return suite


def validate_df(df):
    """Validate a pandas dataframe against the suite and return the result object."""
    context = gx.get_context(mode="ephemeral")
    suite = context.suites.add(build_suite())
    source = context.data_sources.add_pandas("bronze")
    asset = source.add_dataframe_asset(name="yellow_trips")
    batch_def = asset.add_batch_definition_whole_dataframe("whole")
    validation = context.validation_definitions.add(
        gx.ValidationDefinition(data=batch_def, suite=suite, name="bronze_yellow_trips_vd")
    )
    return validation.run(batch_parameters={"dataframe": df})


def assert_valid(df) -> None:
    """Raise ValueError if any expectation fails."""
    result = validate_df(df)
    if not result.success:
        failed = [
            r["expectation_config"]["type"]
            for r in result["results"]
            if not r["success"]
        ]
        raise ValueError(f"trip quality suite failed: {failed}")
