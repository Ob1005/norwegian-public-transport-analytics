from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    StringType,
    StructField,
    StructType,
)

LINE_SCHEMA = StructType(
    [
        StructField("id", StringType(), True),
        StructField("publicCode", StringType(), True),
        StructField("name", StringType(), True),
        StructField("transportMode", StringType(), True),
    ]
)

JOURNEY_PATTERN_SCHEMA = StructType(
    [
        StructField("line", LINE_SCHEMA, True),
    ]
)

SERVICE_JOURNEY_SCHEMA = StructType(
    [
        StructField("id", StringType(), True),
        StructField("journeyPattern", JOURNEY_PATTERN_SCHEMA, True),
    ]
)

DESTINATION_SCHEMA = StructType(
    [
        StructField("frontText", StringType(), True),
    ]
)

QUAY_SCHEMA = StructType(
    [
        StructField("id", StringType(), True),
        StructField("name", StringType(), True),
    ]
)

ESTIMATED_CALL_SCHEMA = StructType(
    [
        StructField("realtime", BooleanType(), True),
        StructField("aimedDepartureTime", StringType(), True),
        StructField("expectedDepartureTime", StringType(), True),
        StructField("actualDepartureTime", StringType(), True),
        StructField("quay", QUAY_SCHEMA, True),
        StructField("destinationDisplay", DESTINATION_SCHEMA, True),
        StructField("serviceJourney", SERVICE_JOURNEY_SCHEMA, True),
    ]
)

STOP_PLACE_SCHEMA = StructType(
    [
        StructField("id", StringType(), True),
        StructField("name", StringType(), True),
        StructField(
            "estimatedCalls",
            ArrayType(ESTIMATED_CALL_SCHEMA),
            True,
        ),
    ]
)

DATA_SCHEMA = StructType(
    [
        StructField("stopPlace", STOP_PLACE_SCHEMA, True),
    ]
)

DEPARTURE_SNAPSHOT_SCHEMA = StructType(
    [
        StructField("collected_at_utc", StringType(), False),
        StructField("stop_place_id", StringType(), False),
        StructField("data", DATA_SCHEMA, False),
    ]
)