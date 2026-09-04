from datetime import date

import pandas as pd
import pytest

from transport_analytics.analysis.dashboard_data import (
    DashboardFilters,
    build_departure_query,
    calculate_overview,
    elevated_delay_lines,
    partition_sample_groups,
    summarize_delays,
)


def sample_departures() -> pd.DataFrame:
    """Return a small latest-estimate sample for analytical unit tests."""
    return pd.DataFrame(
        [
            {
                "stop_key": 1,
                "stop_name": "Oslo S",
                "line_key": 10,
                "line_public_code": "L1",
                "line_name": "Line one",
                "transport_mode": "rail",
                "delay_seconds": 0,
            },
            {
                "stop_key": 1,
                "stop_name": "Oslo S",
                "line_key": 10,
                "line_public_code": "L1",
                "line_name": "Line one",
                "transport_mode": "rail",
                "delay_seconds": 360,
            },
            {
                "stop_key": 2,
                "stop_name": "Majorstuen",
                "line_key": 20,
                "line_public_code": "5",
                "line_name": "Line five",
                "transport_mode": "tram",
                "delay_seconds": 240,
            },
            {
                "stop_key": 2,
                "stop_name": "Majorstuen",
                "line_key": 20,
                "line_public_code": "5",
                "line_name": "Line five",
                "transport_mode": "tram",
                "delay_seconds": 300,
            },
        ]
    )


def test_departure_query_uses_latest_view_and_parameterized_filters() -> None:
    """Dashboard queries must not count recurring snapshots independently."""
    filters = DashboardFilters(
        start_date=date(2026, 9, 3),
        end_date=date(2026, 9, 4),
        stop_keys=(1, 2),
        transport_modes=("rail",),
        line_keys=(10,),
    )

    query, parameters = build_departure_query(filters)

    assert "analytics.v_latest_departure_estimate" in query
    assert "estimate.stop_key = ANY(%s)" in query
    assert "line.transport_mode = ANY(%s)" in query
    assert "estimate.line_key = ANY(%s)" in query
    assert parameters == [
        date(2026, 9, 3),
        date(2026, 9, 4),
        [1, 2],
        ["rail"],
        [10],
    ]


def test_departure_query_rejects_reversed_dates() -> None:
    """An invalid date range should fail before querying PostgreSQL."""
    filters = DashboardFilters(
        start_date=date(2026, 9, 4),
        end_date=date(2026, 9, 3),
    )

    with pytest.raises(ValueError, match="start date"):
        build_departure_query(filters)


def test_dashboard_summaries_include_rates_and_sample_sizes() -> None:
    """Dashboard aggregates should expose both estimates and denominators."""
    departures = sample_departures()

    overview = calculate_overview(departures)
    by_mode = summarize_delays(departures, ["transport_mode"])
    elevated = elevated_delay_lines(departures, minimum_sample=2)

    assert overview == {
        "departures": 4,
        "stops": 2,
        "lines": 2,
        "average_delay_seconds": 225.0,
        "percent_over_threshold": 75.0,
    }
    rail = by_mode.loc[by_mode["transport_mode"] == "rail"].iloc[0]
    assert rail["departures"] == 2
    assert rail["average_delay_seconds"] == 180
    assert rail["percent_over_threshold"] == 50
    assert elevated.iloc[0]["line_public_code"] == "5"
    assert elevated.iloc[0]["percent_over_threshold"] == 100


def test_elevated_lines_enforces_sample_floor() -> None:
    """Tiny line samples should not appear in elevated-delay rankings."""
    assert elevated_delay_lines(sample_departures(), minimum_sample=3).empty

    with pytest.raises(ValueError, match="at least 1"):
        elevated_delay_lines(sample_departures(), minimum_sample=0)


def test_partition_sample_groups_marks_tiny_modes_insufficient() -> None:
    """Mode comparisons should exclude groups below the documented floor."""
    summary = pd.DataFrame(
        {
            "transport_mode": ["rail", "coach"],
            "departures": [50, 1],
        }
    )

    sufficient, insufficient = partition_sample_groups(
        summary,
        minimum_sample=30,
    )

    assert sufficient["transport_mode"].tolist() == ["rail"]
    assert insufficient["transport_mode"].tolist() == ["coach"]
