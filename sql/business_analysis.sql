-- All results use the latest available expected departure time for each
-- unique service journey at each monitored stop. They are operational
-- estimates, not official final punctuality statistics.

-- 1. Dataset coverage
SELECT
    MIN(date.full_date) AS first_service_date,
    MAX(date.full_date) AS last_service_date,
    COUNT(*) AS unique_departures,
    COUNT(DISTINCT estimate.stop_key) AS monitored_stops,
    COUNT(DISTINCT estimate.line_key) AS distinct_lines
FROM analytics.v_latest_departure_estimate AS estimate
JOIN analytics.dim_date AS date
    ON estimate.date_key = date.date_key;


-- 2. Delay estimates by transport mode
SELECT
    line.transport_mode,
    COUNT(*) AS departures,
    ROUND(AVG(estimate.delay_seconds)::NUMERIC, 1)
        AS average_delay_seconds,
    ROUND(
        PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY estimate.delay_seconds
        )::NUMERIC,
        1
    ) AS median_delay_seconds,
    ROUND(
        PERCENTILE_CONT(0.9) WITHIN GROUP (
            ORDER BY estimate.delay_seconds
        )::NUMERIC,
        1
    ) AS p90_delay_seconds,
    ROUND(
        100.0 * AVG((estimate.delay_seconds > 180)::INTEGER),
        1
    ) AS percent_over_3_minutes,
    ROUND(
        100.0 * AVG((estimate.delay_seconds > 300)::INTEGER),
        1
    ) AS percent_over_5_minutes
FROM analytics.v_latest_departure_estimate AS estimate
JOIN analytics.dim_line AS line
    ON estimate.line_key = line.line_key
GROUP BY line.transport_mode
ORDER BY average_delay_seconds DESC;


-- 3. Delay estimates by monitored stop
SELECT
    stop.stop_name,
    COUNT(*) AS departures,
    ROUND(AVG(estimate.delay_seconds)::NUMERIC, 1)
        AS average_delay_seconds,
    ROUND(
        PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY estimate.delay_seconds
        )::NUMERIC,
        1
    ) AS median_delay_seconds,
    ROUND(
        100.0 * AVG((estimate.delay_seconds > 180)::INTEGER),
        1
    ) AS percent_over_3_minutes
FROM analytics.v_latest_departure_estimate AS estimate
JOIN analytics.dim_stop AS stop
    ON estimate.stop_key = stop.stop_key
GROUP BY stop.stop_name
ORDER BY average_delay_seconds DESC;


-- 4. Delay estimates by local departure hour
SELECT
    estimate.departure_hour,
    COUNT(*) AS departures,
    ROUND(AVG(estimate.delay_seconds)::NUMERIC, 1)
        AS average_delay_seconds,
    ROUND(
        PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY estimate.delay_seconds
        )::NUMERIC,
        1
    ) AS median_delay_seconds,
    ROUND(
        100.0 * AVG((estimate.delay_seconds > 180)::INTEGER),
        1
    ) AS percent_over_3_minutes
FROM analytics.v_latest_departure_estimate AS estimate
GROUP BY estimate.departure_hour
ORDER BY estimate.departure_hour;


-- 5. Lines with the highest estimated-delay rates
-- Minimum 30 observed departures avoids ranking tiny samples.
SELECT
    line.transport_mode,
    line.line_public_code,
    line.line_name,
    COUNT(*) AS departures,
    ROUND(AVG(estimate.delay_seconds)::NUMERIC, 1)
        AS average_delay_seconds,
    ROUND(
        100.0 * AVG((estimate.delay_seconds > 180)::INTEGER),
        1
    ) AS percent_over_3_minutes
FROM analytics.v_latest_departure_estimate AS estimate
JOIN analytics.dim_line AS line
    ON estimate.line_key = line.line_key
GROUP BY
    line.line_id,
    line.transport_mode,
    line.line_public_code,
    line.line_name
HAVING COUNT(*) >= 30
ORDER BY percent_over_3_minutes DESC, departures DESC
LIMIT 15;