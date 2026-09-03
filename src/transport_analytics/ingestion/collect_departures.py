import json
from datetime import UTC, datetime
from pathlib import Path

from transport_analytics.ingestion.journey_planner import get_departures


DEFAULT_OUTPUT_DIRECTORY = Path("data/raw/departures")
OSLO_S_ID = "NSR:StopPlace:59872"


def save_departure_snapshot(
    stop_place_id: str,
    output_directory: Path = DEFAULT_OUTPUT_DIRECTORY,
) -> Path:
    """Collect and save one raw departure-board snapshot."""
    collected_at = datetime.now(UTC)
    data = get_departures(stop_place_id, number_of_departures=20)

    snapshot = {
        "collected_at_utc": collected_at.isoformat(),
        "stop_place_id": stop_place_id,
        "data": data,
    }

    date_directory = output_directory / collected_at.strftime("%Y-%m-%d")
    date_directory.mkdir(parents=True, exist_ok=True)

    filename = f"{collected_at.strftime('%Y%m%dT%H%M%SZ')}.json"
    output_path = date_directory / filename

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(snapshot, file, ensure_ascii=False, indent=2)

    return output_path


def main() -> None:
    """Collect and save one Oslo S departure snapshot."""
    output_path = save_departure_snapshot(OSLO_S_ID)
    print(f"Saved departure snapshot to {output_path}")


if __name__ == "__main__":
    main()