from datetime import datetime, timezone
from unittest.mock import patch

from rest_framework.test import APIRequestFactory

from routing.views import corridor_forecast
from routing.services.weather import CheckpointForecast, WeatherProviderError
from routing.services.risk import WeatherConditions


def request_data():
    return {
        "departure_time": "2026-11-05T10:00:00+00:00",
        "load_weight_lb": 35000,
        "points": [
            {"latitude": 39.74, "longitude": -104.99},
            {"latitude": 38.83, "longitude": -104.82},
        ],
    }


def post(data):
    return corridor_forecast(APIRequestFactory().post("/api/weather/corridor/", data, format="json"))


def test_corridor_returns_49_hourly_samples_and_load_adjusted_risk():
    with patch("routing.views.OpenMeteoClient") as weather_class:
        weather_class.return_value.get_forecast.side_effect = (
            lambda lat, lon, eta: CheckpointForecast(
                eta.isoformat(), eta.isoformat(), WeatherConditions(47, 0, 0)
            )
        )
        response = post(request_data())
        assert response.status_code == 200
        assert len(response.data["points"]) == 2
        assert len(response.data["points"][0]["hours"]) == 49
        assert response.data["points"][0]["hours"][0]["risk"] == "NO_TRAVEL"
        assert weather_class.return_value.prefetch.call_count == 1


def test_corridor_rejects_invalid_coordinates():
    data = request_data()
    data["points"][0]["latitude"] = 120
    assert post(data).status_code == 400


def test_corridor_rejects_unbounded_points():
    data = request_data()
    data["points"] = data["points"] * 21
    assert post(data).status_code == 400


def test_corridor_rejects_naive_departure():
    data = request_data()
    data["departure_time"] = "2026-11-05T10:00:00"
    assert post(data).status_code == 400


def test_corridor_weather_failure_is_not_silently_substituted():
    with patch("routing.views.OpenMeteoClient") as weather_class:
        weather_class.return_value.prefetch.side_effect = WeatherProviderError("forecast unavailable")
        response = post(request_data())
    assert response.status_code == 502
