import json

from transport_analytics.ingestion.collect_departures import (
    save_departure_snapshot,
)


def test_save_departure_snapshot(monkeypatch, tmp_path) -> None:
    """The collector should save API data as a timestamped JSON file."""
    fake_data = {
        "stopPlace": {
            "name": "Oslo S",
            "estimatedCalls": [],
        }
    }

    def fake_get_departures(stop_place_id, number_of_departures):
        assert stop_place_id == "NSR:StopPlace:59872"
        assert number_of_departures == 20
        return fake_data

    monkeypatch.setattr(
        "transport_analytics.ingestion.collect_departures.get_departures",
        fake_get_departures,
    )

    output_path = save_departure_snapshot(
        "NSR:StopPlace:59872",
        output_directory=tmp_path,
    )

    assert output_path.exists()
    assert output_path.suffix == ".json"
    assert output_path.parent.parent == tmp_path

    saved_snapshot = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved_snapshot["stop_place_id"] == "NSR:StopPlace:59872"
    assert saved_snapshot["data"] == fake_data
    assert saved_snapshot["collected_at_utc"].endswith("+00:00")