from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from transport_analytics.processing.departures_etl import (
    PROCESSED_DATA_PATH,
    create_spark_session,
)


def build_quality_summary(departures: DataFrame) -> DataFrame:
    """Calculate core quality metrics for processed departures."""
    return departures.agg(
        F.count("*").alias("total_observations"),
        F.countDistinct("stop_place_id").alias("distinct_stops"),
        F.countDistinct("line_id").alias("distinct_lines"),
        F.sum(F.col("realtime").cast("integer")).alias(
            "realtime_observations"
        ),
        F.sum(
            F.when(F.col("service_journey_id").isNull(), 1).otherwise(0)
        ).alias("missing_service_journey_id"),
        F.sum(
            F.when(F.col("aimed_departure_utc").isNull(), 1).otherwise(0)
        ).alias("missing_aimed_departure"),
        F.sum(
            F.when(F.col("expected_departure_utc").isNull(), 1).otherwise(0)
        ).alias("missing_expected_departure"),
        F.sum(
            F.when(F.col("delay_seconds") < 0, 1).otherwise(0)
        ).alias("negative_delay_observations"),
        F.sum(
            F.when(F.abs(F.col("delay_seconds")) > 7200, 1).otherwise(0)
        ).alias("delay_over_two_hours"),
        F.round(F.avg("delay_seconds"), 2).alias("average_delay_seconds"),
        F.expr(
            "percentile_approx(delay_seconds, 0.5)"
        ).alias("median_delay_seconds"),
        F.max("delay_seconds").alias("maximum_delay_seconds"),
    )


def main(
    processed_path: Path = PROCESSED_DATA_PATH,
) -> None:
    """Print overall and transport-mode data-quality summaries."""
    if not processed_path.exists():
        raise FileNotFoundError(
            f"Processed data directory not found: {processed_path}"
        )

    spark = create_spark_session()

    try:
        departures = spark.read.parquet(str(processed_path))

        print("Overall data-quality summary:")
        build_quality_summary(departures).show(
            truncate=False,
            vertical=True,
        )

        print("Observations by transport mode:")
        (
            departures.groupBy("transport_mode")
            .agg(
                F.count("*").alias("observations"),
                F.round(F.avg("delay_seconds"), 2).alias(
                    "average_delay_seconds"
                ),
                F.expr(
                    "percentile_approx(delay_seconds, 0.5)"
                ).alias("median_delay_seconds"),
            )
            .orderBy(F.desc("observations"))
            .show(truncate=False)
        )
    finally:
        spark.stop()


if __name__ == "__main__":
    main()