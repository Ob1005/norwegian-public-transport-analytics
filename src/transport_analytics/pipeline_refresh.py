import logging
from collections.abc import Callable, Sequence

from transport_analytics.database.analytics_views import (
    run_analytics_view_creation,
)
from transport_analytics.database.warehouse_loader import run_warehouse_load
from transport_analytics.processing.departures_etl import run_etl

LOGGER = logging.getLogger(__name__)

PipelineStage = tuple[str, Callable[[], object]]


def default_pipeline_stages() -> tuple[PipelineStage, ...]:
    """Return the ordered stages in one local pipeline refresh."""
    return (
        ("PySpark ETL", run_etl),
        ("PostgreSQL warehouse load", run_warehouse_load),
        ("analytical-view creation", run_analytics_view_creation),
    )


def run_pipeline_refresh(
    stages: Sequence[PipelineStage] | None = None,
) -> None:
    """Run every refresh stage in order and identify a failing stage."""
    selected_stages = default_pipeline_stages() if stages is None else stages
    LOGGER.info("Starting pipeline refresh with %d stages", len(selected_stages))

    for stage_number, (stage_name, stage) in enumerate(selected_stages, start=1):
        LOGGER.info(
            "Stage %d/%d started: %s",
            stage_number,
            len(selected_stages),
            stage_name,
        )
        try:
            stage()
        except Exception as error:
            message = f"Pipeline refresh failed during {stage_name}: {error}"
            LOGGER.exception(message)
            raise RuntimeError(message) from error
        LOGGER.info(
            "Stage %d/%d complete: %s",
            stage_number,
            len(selected_stages),
            stage_name,
        )

    LOGGER.info("Pipeline refresh completed successfully")


def main() -> None:
    """Run the local ETL, warehouse load, and analytical-view refresh."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    try:
        run_pipeline_refresh()
    except RuntimeError as error:
        LOGGER.error("Refresh stopped. Resolve the reported stage and retry.")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
