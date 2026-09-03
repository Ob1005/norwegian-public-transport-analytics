from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from transport_analytics.processing.departure_schema import (
    DEPARTURE_SNAPSHOT_SCHEMA,
)

RAW_DATA_PATH = Path("data/raw/departures")
PROCESSED_DATA_PATH = Path("data/processed/departures")


def create_spark_session() -> SparkSession:
    """Create a local Spark session using UTC internally."""
    return (
        SparkSession.builder.master("local[*]")
        .appName("norwegian-public-transport-etl")
        .config("spark.sql.session.timeZone", "UTC")
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
    spark = create_spark_session()

    try:
        raw_snapshots = read_raw_snapshots(spark)
        departures = transform_departures(raw_snapshots)

        print(f"Raw snapshots: {raw_snapshots.count()}")
        print(f"Processed departure observations: {departures.count()}")

        departures.select(
            "stop_name",
            "line_public_code",
            "transport_mode",
            "destination",
            "delay_seconds",
        ).show(10, truncate=False)

        write_processed_departures(departures)
        print(f"Processed data written to {PROCESSED_DATA_PATH}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()