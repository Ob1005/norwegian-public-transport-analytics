import pytest

from transport_analytics.database.connection import (
    required_environment_value,
)


def test_required_environment_value(monkeypatch) -> None:
    """A configured value should be returned."""
    monkeypatch.setenv("TEST_DATABASE_SETTING", "configured-value")

    result = required_environment_value("TEST_DATABASE_SETTING")

    assert result == "configured-value"


def test_required_environment_value_raises_when_missing(
    monkeypatch,
) -> None:
    """A missing required value should produce a clear error."""
    monkeypatch.delenv("TEST_DATABASE_SETTING", raising=False)

    with pytest.raises(
        ValueError,
        match="Required environment variable is missing",
    ):
        required_environment_value("TEST_DATABASE_SETTING")