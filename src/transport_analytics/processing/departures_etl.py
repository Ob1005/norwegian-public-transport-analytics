import logging
import os
import sys
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from transport_analytics.processing.departure_schema import (
    DEPARTURE_SNAPSHOT_SCHEMA,
)

RAW_DATA_PATH = Path("data/raw/departures")
PROCESSED_DATA_PATH = Path("data/processed/departures")

LOGGER = logging.getLogger(__name__)


def create_spark_session(master: str = "local[*]") -> SparkSession:
    """Create a local Spark session using UTC and the active Python."""
    python_executable = sys.executable
    os.environ["PYSPARK_PYTHON"] = python_executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = python_executable
    return (
        SparkSession.builder.master(master)
        .appName("norwegian-public-transport-etl")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.pyspark.python", python_executable)
        .config("spark.pyspark.driver.python", python_executable)
        .getOrCreate()
    )


def read_raw_snapshots(
    spark: SparkSession,
    input_path: Path = RAW_DATA_PATH,
) -> DataFrame:
    """Read all nested raw JSON snapshots using an explicit schema."""
    if not input_path.exists():
        raise FileNotFoundError(f"Raw data directory not found: {input_path}")

    return (
        spark.read.option("multiLine", True)
        .option("recursiveFileLookup", True)
        .option("pathGlobFilter", "*.json")
        .schema(DEPARTURE_SNAPSHOT_SCHEMA)
        .json(str(input_path))
    )


def transform_departures(snapshots: DataFrame) -> DataFrame:
    """Flatten Entur snapshots and create analytical features."""
    departures = snapshots.withColumn(
        "call",
        F.explode("data.stopPlace.estimatedCalls"),
    )

    flattened = departures.select(
        F.to_timestamp("collected_at_utc").alias("collected_at_utc"),
        F.coalesce(
            F.col("data.stopPlace.id"),
            F.col("stop_place_id"),
        ).alias("stop_place_id"),
        F.col("data.stopPlace.name").alias("stop_name"),
        F.col("call.quay.id").alias("quay_id"),
        F.col("call.quay.name").alias("quay_name"),
        F.col("call.serviceJourney.id").alias("service_journey_id"),
        F.col("call.serviceJourney.journeyPattern.line.id").alias("line_id"),
        F.col(
            "call.serviceJourney.journeyPattern.line.publicCode"
        ).alias("line_public_code"),
        F.col(
            "call.serviceJourney.journeyPattern.line.name"
        ).alias("line_name"),
        F.col(
            "call.serviceJourney.journeyPattern.line.transportMode"
        ).alias("transport_mode"),
        F.col("call.destinationDisplay.frontText").alias("destination"),
        F.col("call.realtime").alias("realtime"),
        F.to_timestamp("call.aimedDepartureTime").alias(
            "aimed_departure_utc"
        ),
        F.to_timestamp("call.expectedDepartureTime").alias(
            "expected_departure_utc"
        ),
        F.to_timestamp("call.actualDepartureTime").alias(
            "actual_departure_utc"
        ),
    )

    transformed = (
        flattened.withColumn(
            "delay_seconds",
            F.col("expected_departure_utc").cast("long")
            - F.col("aimed_departure_utc").cast("long"),
        )
        .withColumn(
            "expected_departure_local",
            F.from_utc_timestamp(
                "expected_departure_utc",
                "Europe/Oslo",
            ),
        )
        .withColumn(
            "service_date",
            F.to_date("expected_departure_local"),
        )
        .withColumn(
            "departure_hour",
            F.hour("expected_departure_local"),
        )
        .withColumn(
            "weekday_number",
            F.dayofweek("expected_departure_local"),
        )
        .withColumn(
            "is_weekend",
            F.col("weekday_number").isin(1, 7),
        )
        .filter(
            F.col("stop_place_id").isNotNull()
            & F.col("service_journey_id").isNotNull()
            & F.col("aimed_departure_utc").isNotNull()
            & F.col("expected_departure_utc").isNotNull()
        )
        .dropDuplicates(
            [
                "collected_at_utc",
                "stop_place_id",
                "service_journey_id",
                "quay_id",
                "aimed_departure_utc",
            ]
        )
    )

    return transformed


def run_etl(
    input_path: Path = RAW_DATA_PATH,
    output_path: Path = PROCESSED_DATA_PATH,
) -> tuple[int, int]:
    """Run raw-to-Parquet ETL and return input and output row counts."""
    LOGGER.info("Starting PySpark ETL from %s", input_path)
    spark = create_spark_session()

    try:
        raw_snapshots = read_raw_snapshots(spark, input_path)
        departures = transform_departures(raw_snapshots).cache()
        raw_count = raw_snapshots.count()
        processed_count = departures.count()

        if raw_count == 0:
            raise ValueError(f"No JSON snapshots found in {input_path}")
        if processed_count == 0:
            raise ValueError(
                "ETL produced no valid departure observations; "
                "check the raw snapshot structure and required fields"
            )

        write_processed_departures(departures, output_path)
        LOGGER.info(
            "PySpark ETL complete: %d snapshots -> %d observations in %s",
            raw_count,
            processed_count,
            output_path,
        )
        return raw_count, processed_count
    finally:
        spark.stop()


def write_processed_departures(
    departures: DataFrame,
    output_path: Path = PROCESSED_DATA_PATH,
) -> None:
    """Write transformed departures as partitioned Parquet files."""
    (
        departures.write.mode("overwrite")
        .partitionBy("service_date")
        .parquet(str(output_path))
    )


def main() -> None:
    """Run the complete raw-to-Parquet transformation."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    raw_count, processed_count = run_etl()
    print(f"Raw snapshots: {raw_count}")
    print(f"Processed departure observations: {processed_count}")


if __name__ == "__main__":
    main()
