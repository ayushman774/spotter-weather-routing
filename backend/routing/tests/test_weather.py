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

def test_batch_prefetch_deduplicates_coordinates_and_reuses_cache():
    calls = []

    def handler(request):
        calls.append(request)
        latitudes = request.url.params["latitude"].split(",")
        longitudes = request.url.params["longitude"].split(",")
        assert len(latitudes) == len(longitudes)
        payload = [
            {
                "hourly": {
                    "time": ["2026-11-04T15:00", "2026-11-04T16:00"],
                    "wind_speed_10m": [20, 35],
                    "rain": [0, 0.1],
                    "snowfall": [0, 0],
                }
            }
            for _ in latitudes
        ]
        return httpx.Response(200, json=payload if len(payload) > 1 else payload[0])

    client = OpenMeteoClient(transport=httpx.MockTransport(handler))
    checkpoints = [
        {"latitude": 39.74, "longitude": -104.98, "eta": "2026-11-04T15:00:00+00:00"},
        {"latitude": 39.5, "longitude": -104.9, "eta": "2026-11-04T15:00:00+00:00"},
        {"latitude": 39.74, "longitude": -104.98, "eta": "2026-11-04T16:00:00+00:00"},
    ]
    client.prefetch(checkpoints)
    assert len(calls) == 1
    assert len(calls[0].url.params["latitude"].split(",")) == 2
    first = client.get_forecast(39.74, -104.98, datetime(2026, 11, 4, 15, tzinfo=timezone.utc))
    later = client.get_forecast(39.74, -104.98, datetime(2026, 11, 4, 16, tzinfo=timezone.utc))
    assert first.conditions.wind_mph == 20
    assert later.conditions.wind_mph == 35
    assert len(calls) == 1
    client.prefetch(checkpoints)
    assert len(calls) == 1


def test_batch_prefetch_rejects_mismatched_response_count():
    client = client_with_payload({"hourly": {}})
    checkpoints = [
        {"latitude": 39.74, "longitude": -104.98, "eta": "2026-11-04T15:00:00+00:00"},
        {"latitude": 39.5, "longitude": -104.9, "eta": "2026-11-04T15:00:00+00:00"},
    ]
    with pytest.raises(WeatherProviderError):
        client.prefetch(checkpoints)


def test_batch_prefetch_splits_large_requests():
    calls = []

    def handler(request):
        coordinates = request.url.params["latitude"].split(",")
        calls.append(len(coordinates))
        data = {
            "hourly": {
                "time": ["2026-11-04T15:00"],
                "wind_speed_10m": [20],
                "rain": [0],
                "snowfall": [0],
            }
        }
        return httpx.Response(200, json=[data for _ in coordinates])

    client = OpenMeteoClient(transport=httpx.MockTransport(handler))
    checkpoints = [
        {"latitude": 30 + index * 0.01, "longitude": -100, "eta": "2026-11-04T15:00:00+00:00"}
        for index in range(30)
    ]
    client.prefetch(checkpoints)
    assert calls == [25, 5]
    assert client.get_forecast(
        30.29, -100, datetime(2026, 11, 4, 15, tzinfo=timezone.utc)
    ).conditions.wind_mph == 20


def test_failed_batch_does_not_cache_invalid_payload():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=[
            {"hourly": {"time": ["2026-11-04T15:00"], "wind_speed_10m": [20], "rain": [0], "snowfall": [0]}},
            {"hourly": {"time": ["2026-11-04T15:00"], "wind_speed_10m": [None], "rain": [0], "snowfall": [0]}},
        ])

    client = OpenMeteoClient(transport=httpx.MockTransport(handler))
    checkpoints = [
        {"latitude": 39.74, "longitude": -104.98, "eta": "2026-11-04T15:00:00+00:00"},
        {"latitude": 39.5, "longitude": -104.9, "eta": "2026-11-04T15:00:00+00:00"},
    ]
    with pytest.raises(WeatherProviderError):
        client.prefetch(checkpoints)
    with pytest.raises(WeatherProviderError):
        client.prefetch(checkpoints)
    assert len(calls) == 2
