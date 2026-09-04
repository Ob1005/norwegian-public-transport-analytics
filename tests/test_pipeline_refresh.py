import pytest

from transport_analytics.pipeline_refresh import run_pipeline_refresh


def test_pipeline_refresh_runs_stages_in_order() -> None:
    """The documented command should preserve the required stage order."""
    completed = []
    stages = [
        ("PySpark ETL", lambda: completed.append("etl")),
        ("PostgreSQL load", lambda: completed.append("warehouse")),
        ("analytical views", lambda: completed.append("views")),
    ]

    run_pipeline_refresh(stages)

    assert completed == ["etl", "warehouse", "views"]


def test_pipeline_refresh_names_failure_and_stops() -> None:
    """A stage failure should be actionable and prevent later stages."""
    completed = []

    def fail_load() -> None:
        raise OSError("database unavailable")

    stages = [
        ("PySpark ETL", lambda: completed.append("etl")),
        ("PostgreSQL load", fail_load),
        ("analytical views", lambda: completed.append("views")),
    ]

    with pytest.raises(
        RuntimeError,
        match="failed during PostgreSQL load: database unavailable",
    ):
        run_pipeline_refresh(stages)

    assert completed == ["etl"]
