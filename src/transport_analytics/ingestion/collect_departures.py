import json
from datetime import UTC, datetime
from pathlib import Path

from transport_analytics.ingestion.journey_planner import get_departures

DEFAULT_OUTPUT_DIRECTORY = Path("data/raw/departures")

OSLO_STOP_PLACES = {
    "Oslo S": "NSR:StopPlace:59872",
    "Jernbanetorget": "NSR:StopPlace:58366",
    "Nationaltheatret": "NSR:StopPlace:58404",
    "Majorstuen": "NSR:StopPlace:58381",
    "Nydalen": "NSR:StopPlace:59605",
}


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

    stop_directory_name = stop_place_id.replace(":", "_")
    snapshot_directory = (
        output_directory
        / collected_at.strftime("%Y-%m-%d")
        / stop_directory_name
    )
    snapshot_directory.mkdir(parents=True, exist_ok=True)

    filename = f"{collected_at.strftime('%Y%m%dT%H%M%SZ')}.json"
    output_path = snapshot_directory / filename

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(snapshot, file, ensure_ascii=False, indent=2)

    return output_path


def main() -> None:
    """Collect one departure snapshot for each configured Oslo stop."""
    for stop_name, stop_place_id in OSLO_STOP_PLACES.items():
        output_path = save_departure_snapshot(stop_place_id)
        print(f"Saved {stop_name} snapshot to {output_path}")


if __name__ == "__main__":
    main()