CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    week_of_year INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_name TEXT NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics.dim_stop (
    stop_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stop_place_id TEXT NOT NULL UNIQUE,
    stop_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics.dim_quay (
    quay_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    quay_id TEXT NOT NULL UNIQUE,
    quay_name TEXT,
    stop_key BIGINT NOT NULL
        REFERENCES analytics.dim_stop(stop_key)
);

CREATE TABLE IF NOT EXISTS analytics.dim_line (
    line_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    line_id TEXT NOT NULL UNIQUE,
    line_public_code TEXT,
    line_name TEXT,
    transport_mode TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analytics.stg_departure_observation (
    collected_at_utc TIMESTAMPTZ NOT NULL,
    stop_place_id TEXT NOT NULL,
    stop_name TEXT NOT NULL,
    quay_id TEXT,
    quay_name TEXT,
    line_id TEXT NOT NULL,
    line_public_code TEXT,
    line_name TEXT,
    transport_mode TEXT NOT NULL,
    service_journey_id TEXT NOT NULL,
    destination TEXT,
    realtime BOOLEAN NOT NULL,
    aimed_departure_utc TIMESTAMPTZ NOT NULL,
    expected_departure_utc TIMESTAMPTZ NOT NULL,
    actual_departure_utc TIMESTAMPTZ,
    delay_seconds INTEGER NOT NULL,
    departure_hour SMALLINT NOT NULL,
    service_date DATE NOT NULL
);
CREATE TABLE IF NOT EXISTS analytics.fact_departure_observation (
    observation_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    collected_at_utc TIMESTAMPTZ NOT NULL,
    date_key INTEGER NOT NULL
        REFERENCES analytics.dim_date(date_key),
    stop_key BIGINT NOT NULL
        REFERENCES analytics.dim_stop(stop_key),
    quay_key BIGINT
        REFERENCES analytics.dim_quay(quay_key),
    line_key BIGINT NOT NULL
        REFERENCES analytics.dim_line(line_key),
    service_journey_id TEXT NOT NULL,
    destination TEXT,
    realtime BOOLEAN NOT NULL,
    aimed_departure_utc TIMESTAMPTZ NOT NULL,
    expected_departure_utc TIMESTAMPTZ NOT NULL,
    actual_departure_utc TIMESTAMPTZ,
    delay_seconds INTEGER NOT NULL,
    departure_hour SMALLINT NOT NULL
        CHECK (departure_hour BETWEEN 0 AND 23),

    UNIQUE (
        collected_at_utc,
        stop_key,
        service_journey_id,
        aimed_departure_utc
    )
);

CREATE INDEX IF NOT EXISTS idx_fact_departure_date
    ON analytics.fact_departure_observation(date_key);

CREATE INDEX IF NOT EXISTS idx_fact_departure_line
    ON analytics.fact_departure_observation(line_key);

CREATE INDEX IF NOT EXISTS idx_fact_departure_stop
    ON analytics.fact_departure_observation(stop_key);