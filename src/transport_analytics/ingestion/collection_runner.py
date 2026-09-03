import argparse
import time
from datetime import UTC, datetime

from requests import RequestException

from transport_analytics.ingestion.collect_departures import (
    OSLO_STOP_PLACES,
    save_departure_snapshot,
)


def collect_all_stops() -> tuple[int, int]:
    """Collect one snapshot for every configured stop."""
    successful = 0
    failed = 0

    print(f"\nCollection cycle started at {datetime.now(UTC).isoformat()}")

    for stop_name, stop_place_id in OSLO_STOP_PLACES.items():
        try:
            output_path = save_departure_snapshot(stop_place_id)
            successful += 1
            print(f"Saved {stop_name}: {output_path}")
        except (OSError, RequestException, RuntimeError, ValueError) as error:
            failed += 1
            print(f"Failed to collect {stop_name}: {error}")

    print(f"Cycle finished: {successful} successful, {failed} failed")
    return successful, failed


def run_repeated_collection(interval_seconds: int) -> None:
    """Collect repeatedly until the user stops the process."""
    while True:
        cycle_started = time.monotonic()
        collect_all_stops()

        elapsed_seconds = time.monotonic() - cycle_started
        wait_seconds = max(0, interval_seconds - elapsed_seconds)

        print(f"Waiting {wait_seconds:.0f} seconds before the next cycle...")
        time.sleep(wait_seconds)


def main() -> None:
    """Run one collection cycle or start repeated collection."""
    parser = argparse.ArgumentParser(
        description="Collect Entur departure snapshots from Oslo stops."
    )
    parser.add_argument(
        "--repeat",
        action="store_true",
        help="Continue collecting until stopped with Control+C.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=300,
        help="Seconds between cycle start times. Defaults to 300 (5 minutes).",
    )
    arguments = parser.parse_args()

    if arguments.interval_seconds < 60:
        raise ValueError("The collection interval must be at least 60 seconds")

    if arguments.repeat:
        try:
            run_repeated_collection(arguments.interval_seconds)
        except KeyboardInterrupt:
            print("\nCollection stopped by user.")
    else:
        collect_all_stops()


if __name__ == "__main__":
    main()