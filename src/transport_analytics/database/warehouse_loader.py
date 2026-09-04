import logging
from pathlib import Path

from psycopg import Connection
from pyspark.sql import DataFrame

from transport_analytics.database.connection import (
    get_database_connection,
)
from transport_analytics.processing.departures_etl import (
    PROCESSED_DATA_PATH,
    create_spark_session,
)

WAREHOUSE_SQL_PATH = Path("sql/load_warehouse.sql")

LOGGER = logging.getLogger(__name__)

STAGING_COLUMNS = [
    "collected_at_utc",
    "stop_place_id",
    "stop_name",
    "quay_id",
    "quay_name",
    "line_id",
    "line_public_code",
    "line_name",
    "transport_mode",
    "service_journey_id",
    "destination",
    "realtime",
    "aimed_departure_utc",
    "expected_departure_utc",
    "actual_departure_utc",
    "delay_seconds",
    "departure_hour",
    "service_date",
]

COPY_SQL = """
COPY analytics.stg_departure_observation (
    collected_at_utc,
    stop_place_id,
    stop_name,
    quay_id,
    quay_name,
    line_id,
    line_public_code,
    line_name,
    transport_mode,
    service_journey_id,
    destination,
    realtime,
    aimed_departure_utc,
    expected_departure_utc,
    actual_departure_utc,
    delay_seconds,
    departure_hour,
    service_date
)
FROM STDIN
"""


def load_departures(
    departures: DataFrame,
    connection: Connection,
    warehouse_sql_path: Path = WAREHOUSE_SQL_PATH,
) -> tuple[int, int]:
    """Stream processed Spark rows into staging and populate the warehouse."""
    if not warehouse_sql_path.exists():
        raise FileNotFoundError(
            f"Warehouse SQL file not found: {warehouse_sql_path}"
        )

    warehouse_sql = warehouse_sql_path.read_text(encoding="utf-8")
    staged_rows = 0

    with connection.cursor() as cursor:
        cursor.execute("TRUNCATE analytics.stg_departure_observation;")

        with cursor.copy(COPY_SQL) as copy:
            for row in departures.select(*STAGING_COLUMNS).toLocalIterator():
                copy.write_row(tuple(row))
                staged_rows += 1

        cursor.execute(warehouse_sql)
        cursor.execute(
            "SELECT COUNT(*) FROM analytics.fact_departure_observation;"
        )
        fact_rows = cursor.fetchone()[0]

    return staged_rows, fact_rows


def run_warehouse_load(
    processed_path: Path = PROCESSED_DATA_PATH,
) -> tuple[int, int]:
    """Read processed Parquet and load it into the PostgreSQL warehouse."""
    if not processed_path.exists():
        raise FileNotFoundError(
            f"Processed data directory not found: {processed_path}. "
            "Run the PySpark ETL stage first."
        )

    LOGGER.info("Loading processed departures from %s", processed_path)
    spark = create_spark_session()

    try:
        departures = spark.read.parquet(str(processed_path))

        with get_database_connection() as connection:
            staged_rows, fact_rows = load_departures(departures, connection)

        LOGGER.info(
            "Warehouse load complete: %d staged rows; %d fact rows available",
            staged_rows,
            fact_rows,
        )
        return staged_rows, fact_rows
    finally:
        spark.stop()


def main() -> None:
    """Load processed Parquet departures into PostgreSQL."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    staged_rows, fact_rows = run_warehouse_load()
    print(f"Rows copied to staging: {staged_rows}")
    print(f"Rows available in fact table: {fact_rows}")


if __name__ == "__main__":
    main()
