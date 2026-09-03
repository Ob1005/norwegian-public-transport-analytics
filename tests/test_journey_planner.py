from transport_analytics.ingestion.journey_planner import (
    BASE_URL,
    get_departures,
)


class FakeResponse:
    """Replacement for a Journey Planner HTTP response during testing."""

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {
            "data": {
                "stopPlace": {
                    "name": "Oslo S",
                    "estimatedCalls": [],
                }
            }
        }


def test_get_departures_sends_correct_request(monkeypatch) -> None:
    """The client should send the expected GraphQL request."""
    monkeypatch.setenv(
        "ENTUR_CLIENT_NAME",
        "test-norwegian-public-transport-analytics",
    )

    def fake_post(url, headers, json, timeout):
        assert url == BASE_URL
        assert headers["ET-Client-Name"] == (
            "test-norwegian-public-transport-analytics"
        )
        assert headers["Content-Type"] == "application/json"
        assert json["variables"] == {
            "stopPlaceId": "NSR:StopPlace:59872",
            "numberOfDepartures": 5,
        }
        assert timeout == 30
        return FakeResponse()

    monkeypatch.setattr(
        "transport_analytics.ingestion.journey_planner.requests.post",
        fake_post,
    )

    result = get_departures("NSR:StopPlace:59872")

    assert result["stopPlace"]["name"] == "Oslo S"