"""Unit tests for Open-Meteo checkpoint forecast adapter."""

from datetime import datetime, timezone

import httpx
import pytest

from routing.services.weather import OpenMeteoClient, WeatherProviderError


def client_with_payload(payload, status=200):
    def handler(request):
        assert request.url.params["timezone"] == "UTC"
        assert request.url.params["wind_speed_unit"] == "mph"
        assert request.url.params["precipitation_unit"] == "inch"
        return httpx.Response(status, json=payload)

    return OpenMeteoClient(transport=httpx.MockTransport(handler))


def test_matches_nearest_hour_and_converts_snowfall():
    client = client_with_payload({
        "hourly": {
            "time": ["2026-11-04T15:00", "2026-11-04T16:00"],
            "wind_speed_10m": [20, 40],
            "rain": [0.1, 0.25],
            "snowfall": [0, 2.54],
        }
    })
    result = client.get_forecast(
        39.74, -104.98, datetime.fromisoformat("2026-11-04T08:40:00-07:00")
    )
    assert result.forecast_time == "2026-11-04T16:00:00+00:00"
    assert result.conditions.wind_mph == 40
    assert result.conditions.rain_in_per_hr == 0.25
    assert result.conditions.snow_in_per_hr == pytest.approx(1.0)


def test_missing_measurement_fails_closed():
    client = client_with_payload({
        "hourly": {
            "time": ["2026-11-04T15:00"],
            "wind_speed_10m": [None],
            "rain": [0],
            "snowfall": [0],
        }
    })
    with pytest.raises(WeatherProviderError):
        client.get_forecast(39.74, -104.98, datetime(2026, 11, 4, 15, tzinfo=timezone.utc))


def test_eta_outside_forecast_coverage_fails():
    client = client_with_payload({
        "hourly": {
            "time": ["2026-11-04T15:00"],
            "wind_speed_10m": [20],
            "rain": [0],
            "snowfall": [0],
        }
    })
    with pytest.raises(WeatherProviderError):
        client.get_forecast(39.74, -104.98, datetime(2026, 11, 6, 15, tzinfo=timezone.utc))


def test_http_failure_is_wrapped():
    client = client_with_payload({"reason": "unavailable"}, status=503)
    with pytest.raises(WeatherProviderError):
        client.get_forecast(39.74, -104.98, datetime(2026, 11, 4, 15, tzinfo=timezone.utc))


def test_naive_eta_is_rejected():
    client = client_with_payload({})
    with pytest.raises(ValueError):
        client.get_forecast(39.74, -104.98, datetime(2026, 11, 4, 15))


def test_invalid_coordinates_are_rejected():
    client = client_with_payload({})
    with pytest.raises(ValueError):
        client.get_forecast(100, 0, datetime(2026, 11, 4, 15, tzinfo=timezone.utc))
