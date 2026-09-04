CREATE OR REPLACE VIEW analytics.v_latest_departure_estimate AS
WITH ranked_observations AS (
    SELECT
        observation.*,
        ROW_NUMBER() OVER (
            PARTITION BY
                observation.stop_key,
                observation.service_journey_id,
                observation.aimed_departure_utc
            ORDER BY observation.collected_at_utc DESC
        ) AS observation_rank
    FROM analytics.fact_departure_observation AS observation
)
SELECT
    ranked.observation_key,
    ranked.collected_at_utc,
    ranked.date_key,
    ranked.stop_key,
    ranked.quay_key,
    ranked.line_key,
    ranked.service_journey_id,
    ranked.destination,
    ranked.realtime,
    ranked.aimed_departure_utc,
    ranked.expected_departure_utc,
    ranked.actual_departure_utc,
    ranked.delay_seconds,
    ranked.departure_hour
FROM ranked_observations AS ranked
WHERE ranked.observation_rank = 1;