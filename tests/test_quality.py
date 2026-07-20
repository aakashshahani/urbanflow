"""The bronze trip suite must pass clean data and fail dirty data."""
from __future__ import annotations

import pandas as pd
import pytest

from quality.expectations.trip_suite import assert_valid, validate_df

CLEAN = pd.DataFrame(
    {
        "tpep_pickup_datetime": ["2024-01-01 00:00:00", "2024-01-01 01:00:00"],
        "pulocationid": [100, 132],
        "total_amount": [18.5, 42.0],
        "trip_distance": [3.1, 9.4],
        "passenger_count": [1, 2],
    }
)

DIRTY = pd.DataFrame(
    {
        "tpep_pickup_datetime": ["2024-01-01 00:00:00", None],
        "pulocationid": [100, 132],
        "total_amount": [18.5, -5.0],   # negative fare
        "trip_distance": [3.1, 0.0],    # zero distance
        "passenger_count": [1, 99],     # impossible count
    }
)


def test_clean_data_passes():
    assert validate_df(CLEAN).success is True


def test_dirty_data_fails():
    assert validate_df(DIRTY).success is False


def test_assert_valid_raises_on_dirty():
    with pytest.raises(ValueError):
        assert_valid(DIRTY)
