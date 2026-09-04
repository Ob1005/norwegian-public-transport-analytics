INSERT INTO analytics.dim_date (
    date_key,
    full_date,
    year,
    quarter,
    month,
    month_name,
    week_of_year,
    day_of_week,
    day_name,
    is_weekend
)
SELECT DISTINCT
    TO_CHAR(service_date, 'YYYYMMDD')::INTEGER,
    service_date,
    EXTRACT(YEAR FROM service_date)::INTEGER,
    EXTRACT(QUARTER FROM service_date)::INTEGER,
    EXTRACT(MONTH FROM service_date)::INTEGER,
    TO_CHAR(service_date, 'FMMonth'),
    EXTRACT(WEEK FROM service_date)::INTEGER,
    EXTRACT(ISODOW FROM service_date)::INTEGER,
    TO_CHAR(service_date, 'FMDay'),
    EXTRACT(ISODOW FROM service_date) IN (6, 7)
FROM analytics.stg_departure_observation
ON CONFLICT (full_date) DO NOTHING;

INSERT INTO analytics.dim_stop (
    stop_place_id,
    stop_name
)
SELECT DISTINCT
    stop_place_id,
    stop_name
FROM analytics.stg_departure_observation
ON CONFLICT (stop_place_id)
DO UPDATE SET stop_name = EXCLUDED.stop_name;

INSERT INTO analytics.dim_line (
    line_id,
    line_public_code,
    line_name,
    transport_mode
)
SELECT DISTINCT
    line_id,
    line_public_code,
    line_name,
    transport_mode
FROM analytics.stg_departure_observation
ON CONFLICT (line_id)
DO UPDATE SET
    line_public_code = EXCLUDED.line_public_code,
    line_name = EXCLUDED.line_name,
    transport_mode = EXCLUDED.transport_mode;

INSERT INTO analytics.dim_quay (
    quay_id,
    quay_name,
    stop_key
)
SELECT DISTINCT
    staging.quay_id,
    staging.quay_name,
    stop.stop_key
FROM analytics.stg_departure_observation AS staging
JOIN analytics.dim_stop AS stop
    ON staging.stop_place_id = stop.stop_place_id
WHERE staging.quay_id IS NOT NULL
ON CONFLICT (quay_id)
DO UPDATE SET
    quay_name = EXCLUDED.quay_name,
    stop_key = EXCLUDED.stop_key;

INSERT INTO analytics.fact_departure_observation (
    collected_at_utc,
    date_key,
    stop_key,
    quay_key,
    line_key,
    service_journey_id,
    destination,
    realtime,
    aimed_departure_utc,
    expected_departure_utc,
    actual_departure_utc,
    delay_seconds,
    departure_hour
)
SELECT
    staging.collected_at_utc,
    date.date_key,
    stop.stop_key,
    quay.quay_key,
    line.line_key,
    staging.service_journey_id,
    staging.destination,
    staging.realtime,
    staging.aimed_departure_utc,
    staging.expected_departure_utc,
    staging.actual_departure_utc,
    staging.delay_seconds,
    staging.departure_hour
FROM analytics.stg_departure_observation AS staging
JOIN analytics.dim_date AS date
    ON staging.service_date = date.full_date
JOIN analytics.dim_stop AS stop
    ON staging.stop_place_id = stop.stop_place_id
JOIN analytics.dim_line AS line
    ON staging.line_id = line.line_id
LEFT JOIN analytics.dim_quay AS quay
    ON staging.quay_id = quay.quay_id
ON CONFLICT (
    collected_at_utc,
    stop_key,
    service_journey_id,
    aimed_departure_utc
)
DO UPDATE SET
    expected_departure_utc = EXCLUDED.expected_departure_utc,
    actual_departure_utc = EXCLUDED.actual_departure_utc,
    delay_seconds = EXCLUDED.delay_seconds,
    realtime = EXCLUDED.realtime;