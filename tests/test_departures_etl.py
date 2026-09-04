import sys

import pytest
from pyspark.sql import SparkSession

from transport_analytics.processing.departure_schema import (
    DEPARTURE_SNAPSHOT_SCHEMA,
)
from transport_analytics.processing.departures_etl import (
    create_spark_session,
    transform_departures,
)


@pytest.fixture(scope="module")
def spark() -> SparkSession:
    """Provide one local Spark session for this test module."""
    session = create_spark_session(master="local[1]")
    assert session.conf.get("spark.pyspark.python") == sys.executable
    yield session
    session.stop()


def test_transform_departures_creates_analytical_fields(
    spark: SparkSession,
) -> None:
    """Nested Entur data should become one analytical departure row."""
    snapshot = {
        "collected_at_utc": "2026-09-03T08:00:00+00:00",
        "stop_place_id": "NSR:StopPlace:59872",
        "data": {
            "stopPlace": {
                "id": "NSR:StopPlace:59872",
                "name": "Oslo S",
                "estimatedCalls": [
                    {
                        "realtime": True,
                        "aimedDepartureTime": "2026-09-03T10:00:00+02:00",
                        "expectedDepartureTime": "2026-09-03T10:05:00+02:00",
                        "actualDepartureTime": None,
                        "quay": {
                            "id": "NSR:Quay:1",
                            "name": "Platform 1",
                        },
                        "destinationDisplay": {
                            "frontText": "Lillestrøm",
                        },
                        "serviceJourney": {
                            "id": "TEST:ServiceJourney:1",
                            "journeyPattern": {
                                "line": {
                                    "id": "TEST:Line:1",
                                    "publicCode": "L1",
                                    "name": "Test line",
                                    "transportMode": "rail",
                                }
                            },
                        },
                    }
                ],
            }
        },
    }

    snapshots = spark.createDataFrame(
        [snapshot],
        schema=DEPARTURE_SNAPSHOT_SCHEMA,
    )

    result = transform_departures(snapshots).collect()

    assert len(result) == 1

    departure = result[0]
    assert departure.stop_name == "Oslo S"
    assert departure.line_public_code == "L1"
    assert departure.delay_seconds == 300
    assert departure.departure_hour == 10
    assert departure.is_weekend is False
    snapshot["data"]["stopPlace"]["estimatedCalls"][0][
        "serviceJourney"
    ]["id"] = None

    incomplete_snapshots = spark.createDataFrame(
        [snapshot],
        schema=DEPARTURE_SNAPSHOT_SCHEMA,
    )

    assert transform_departures(incomplete_snapshots).count() == 0
