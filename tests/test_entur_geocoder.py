from transport_analytics.ingestion.entur_geocoder import BASE_URL, search_stops


class FakeResponse:
    """Small replacement for an Entur HTTP response during testing."""

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {
            "features": [
                {
                    "properties": {
                        "name": "Oslo S",
                        "id": "NSR:StopPlace:59872",
                    }
                }
            ]
        }


def test_search_stops_sends_correct_request(monkeypatch) -> None:
    """The client should send the expected header and search parameters."""
    monkeypatch.setenv(
        "ENTUR_CLIENT_NAME",
        "test-norwegian-public-transport-analytics",
    )

    def fake_get(url, headers, params, timeout):
        assert url == BASE_URL
        assert headers["ET-Client-Name"] == (
            "test-norwegian-public-transport-analytics"
        )
        assert params == {
            "text": "Oslo S",
            "lang": "no",
            "size": 5,
            "layers": "venue",
        }
        assert timeout == 30
        return FakeResponse()

    monkeypatch.setattr(
        "transport_analytics.ingestion.entur_geocoder.requests.get",
        fake_get,
    )

    result = search_stops("Oslo S")

    assert result["features"][0]["properties"]["name"] == "Oslo S"