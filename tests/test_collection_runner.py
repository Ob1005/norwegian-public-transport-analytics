from requests import RequestException

from transport_analytics.ingestion import collection_runner


def test_collect_all_stops_continues_after_network_failure(
    monkeypatch,
) -> None:
    """A failed stop should not prevent collection from other stops."""
    test_stops = {
        "Working stop": "stop-1",
        "Failing stop": "stop-2",
    }
    monkeypatch.setattr(
        collection_runner,
        "OSLO_STOP_PLACES",
        test_stops,
    )

    def fake_save_departure_snapshot(stop_place_id):
        if stop_place_id == "stop-2":
            raise RequestException("Temporary network failure")
        return "test-output.json"

    monkeypatch.setattr(
        collection_runner,
        "save_departure_snapshot",
        fake_save_departure_snapshot,
    )

    successful, failed = collection_runner.collect_all_stops()

    assert successful == 1
    assert failed == 1