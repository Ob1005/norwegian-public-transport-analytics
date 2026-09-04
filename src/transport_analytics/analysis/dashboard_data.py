from dataclasses import dataclass
from datetime import date

import pandas as pd
from psycopg import Connection

DELAY_THRESHOLD_SECONDS = 180
MINIMUM_GROUP_SAMPLE = 30

DEPARTURE_COLUMNS = [
    "service_date",
    "stop_key",
    "stop_name",
    "line_key",
    "line_public_code",
    "line_name",
    "transport_mode",
    "departure_hour",
    "delay_seconds",
    "realtime",
    "collected_at_utc",
    "aimed_departure_utc",
    "expected_departure_utc",
]


@dataclass(frozen=True)
class DashboardFilters:
    """Values used to filter latest departure estimates."""

    start_date: date
    end_date: date
    stop_keys: tuple[int, ...] = ()
    transport_modes: tuple[str, ...] = ()
    line_keys: tuple[int, ...] = ()


@dataclass(frozen=True)
class FilterOptions:
    """Available dashboard filter values represented in the warehouse."""

    minimum_date: date
    maximum_date: date
    stops: tuple[tuple[int, str], ...]
    transport_modes: tuple[str, ...]
    lines: tuple[tuple[int, str | None, str | None, str], ...]


def build_departure_query(
    filters: DashboardFilters,
) -> tuple[str, list[object]]:
    """Build a parameterized query against the de-duplicated analytics view."""
    if filters.start_date > filters.end_date:
        raise ValueError("Dashboard start date must not be after end date")

    conditions = ["date.full_date BETWEEN %s AND %s"]
    parameters: list[object] = [filters.start_date, filters.end_date]

    if filters.stop_keys:
        conditions.append("estimate.stop_key = ANY(%s)")
        parameters.append(list(filters.stop_keys))
    if filters.transport_modes:
        conditions.append("line.transport_mode = ANY(%s)")
        parameters.append(list(filters.transport_modes))
    if filters.line_keys:
        conditions.append("estimate.line_key = ANY(%s)")
        parameters.append(list(filters.line_keys))

    query = f"""
        SELECT
            date.full_date AS service_date,
            stop.stop_key,
            stop.stop_name,
            line.line_key,
            line.line_public_code,
            line.line_name,
            line.transport_mode,
            estimate.departure_hour,
            estimate.delay_seconds,
            estimate.realtime,
            estimate.collected_at_utc,
            estimate.aimed_departure_utc,
            estimate.expected_departure_utc
        FROM analytics.v_latest_departure_estimate AS estimate
        JOIN analytics.dim_date AS date
            ON estimate.date_key = date.date_key
        JOIN analytics.dim_stop AS stop
            ON estimate.stop_key = stop.stop_key
        JOIN analytics.dim_line AS line
            ON estimate.line_key = line.line_key
        WHERE {" AND ".join(conditions)}
        ORDER BY estimate.aimed_departure_utc
    """
    return query, parameters


def load_filter_options(connection: Connection) -> FilterOptions:
    """Load only filter values that occur in the latest-estimate view."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT MIN(date.full_date), MAX(date.full_date)
            FROM analytics.v_latest_departure_estimate AS estimate
            JOIN analytics.dim_date AS date
                ON estimate.date_key = date.date_key
            """
        )
        minimum_date, maximum_date = cursor.fetchone()

        if minimum_date is None or maximum_date is None:
            raise ValueError(
                "The latest-departure view contains no data. "
                "Run the pipeline refresh after collecting snapshots."
            )

        cursor.execute(
            """
            SELECT DISTINCT stop.stop_key, stop.stop_name
            FROM analytics.v_latest_departure_estimate AS estimate
            JOIN analytics.dim_stop AS stop
                ON estimate.stop_key = stop.stop_key
            ORDER BY stop.stop_name
            """
        )
        stops = tuple(cursor.fetchall())

        cursor.execute(
            """
            SELECT DISTINCT line.transport_mode
            FROM analytics.v_latest_departure_estimate AS estimate
            JOIN analytics.dim_line AS line
                ON estimate.line_key = line.line_key
            ORDER BY line.transport_mode
            """
        )
        transport_modes = tuple(row[0] for row in cursor.fetchall())

        cursor.execute(
            """
            SELECT DISTINCT
                line.line_key,
                line.line_public_code,
                line.line_name,
                line.transport_mode
            FROM analytics.v_latest_departure_estimate AS estimate
            JOIN analytics.dim_line AS line
                ON estimate.line_key = line.line_key
            ORDER BY line.transport_mode, line.line_public_code, line.line_name
            """
        )
        lines = tuple(cursor.fetchall())

    return FilterOptions(
        minimum_date=minimum_date,
        maximum_date=maximum_date,
        stops=stops,
        transport_modes=transport_modes,
        lines=lines,
    )


def load_departures(
    connection: Connection,
    filters: DashboardFilters,
) -> pd.DataFrame:
    """Load filtered latest estimates from PostgreSQL into a DataFrame."""
    query, parameters = build_departure_query(filters)
    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        rows = cursor.fetchall()

    departures = pd.DataFrame(rows, columns=DEPARTURE_COLUMNS)
    if not departures.empty:
        departures["delay_seconds"] = pd.to_numeric(
            departures["delay_seconds"], errors="coerce"
        )
        departures["departure_hour"] = pd.to_numeric(
            departures["departure_hour"], errors="coerce"
        )
    return departures


def calculate_overview(departures: pd.DataFrame) -> dict[str, float | int]:
    """Calculate headline metrics from a filtered latest-estimate sample."""
    if departures.empty:
        return {
            "departures": 0,
            "stops": 0,
            "lines": 0,
            "average_delay_seconds": 0.0,
            "percent_over_threshold": 0.0,
        }

    return {
        "departures": len(departures),
        "stops": departures["stop_key"].nunique(),
        "lines": departures["line_key"].nunique(),
        "average_delay_seconds": float(departures["delay_seconds"].mean()),
        "percent_over_threshold": float(
            (departures["delay_seconds"] > DELAY_THRESHOLD_SECONDS).mean()
            * 100
        ),
    }


def summarize_delays(
    departures: pd.DataFrame,
    group_columns: list[str],
) -> pd.DataFrame:
    """Aggregate sample size, expected delay, and elevated-delay rate."""
    columns = [
        *group_columns,
        "departures",
        "average_delay_seconds",
        "median_delay_seconds",
        "percent_over_threshold",
    ]
    if departures.empty:
        return pd.DataFrame(columns=columns)

    summarized = (
        departures.assign(
            over_threshold=(
                departures["delay_seconds"] > DELAY_THRESHOLD_SECONDS
            )
        )
        .groupby(group_columns, dropna=False)
        .agg(
            departures=("delay_seconds", "size"),
            average_delay_seconds=("delay_seconds", "mean"),
            median_delay_seconds=("delay_seconds", "median"),
            percent_over_threshold=("over_threshold", "mean"),
        )
        .reset_index()
    )
    summarized["percent_over_threshold"] *= 100
    return summarized


def partition_sample_groups(
    summary: pd.DataFrame,
    minimum_sample: int = MINIMUM_GROUP_SAMPLE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separate sufficiently sampled groups from insufficient groups."""
    if minimum_sample < 1:
        raise ValueError("Minimum group sample must be at least 1")

    sufficient = summary.loc[summary["departures"] >= minimum_sample].copy()
    insufficient = summary.loc[summary["departures"] < minimum_sample].copy()
    return sufficient, insufficient


def elevated_delay_lines(
    departures: pd.DataFrame,
    minimum_sample: int = MINIMUM_GROUP_SAMPLE,
) -> pd.DataFrame:
    """Rank lines by >3-minute expected-delay rate with a sample-size floor."""
    if minimum_sample < 1:
        raise ValueError("Minimum line sample must be at least 1")

    summary = summarize_delays(
        departures,
        [
            "line_key",
            "line_public_code",
            "line_name",
            "transport_mode",
        ],
    )
    sufficient, _ = partition_sample_groups(summary, minimum_sample)
    return (
        sufficient
        .sort_values(
            ["percent_over_threshold", "departures"],
            ascending=[False, False],
        )
        .head(15)
        .reset_index(drop=True)
    )
