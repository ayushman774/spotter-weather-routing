"""API integration tests for opt-in weather assessment."""

from unittest.mock import patch

from routing.services.openrouteservice import Location
from routing.services.risk import WeatherConditions
from routing.services.weather import CheckpointForecast, WeatherProviderError
from routing.tests.test_route_api import make_request


def setup_routes(route_feature, count=2):
    client_patch = patch("routing.views.OpenRouteServiceClient")
    client_class = client_patch.start()
    client = client_class.return_value
    client.geocode.side_effect = [
        Location("Denver", -104.98, 39.74),
        Location("Colorado Springs", -104.81, 38.87),
    ]
    client.get_routes.return_value = [route_feature] * count
    return client_patch


def test_weather_enrichment_and_recommendation(request_data, route_feature):
    request_data["assess_weather"] = True
    route_patch = setup_routes(route_feature)
    try:
        with patch("routing.services.route_scoring.OpenMeteoClient") as weather_class:
            weather_class.return_value.get_forecast.side_effect = (
                lambda lat, lon, eta: CheckpointForecast(
                    eta.isoformat(), eta.isoformat(),
                    WeatherConditions(20, 0, 0),
                )
            )
            response = make_request(request_data)
    finally:
        route_patch.stop()

    assert response.status_code == 200
    assert response.data["weather_assessed"] is True
    assert response.data["recommended_route_id"] == "route-1"
    assert response.data["routes"][0]["safety_rank"] == 1
    assert response.data["routes"][0]["risk_summary"]["severe_miles"] == 0
    assert "weather" in response.data["routes"][0]["checkpoints"][0]


def test_weather_provider_failure_returns_502(request_data, route_feature):
    request_data["assess_weather"] = True
    route_patch = setup_routes(route_feature, count=1)
    try:
        with patch("routing.services.route_scoring.OpenMeteoClient") as weather_class:
            weather_class.return_value.get_forecast.side_effect = WeatherProviderError(
                "forecast unavailable"
            )
            response = make_request(request_data)
    finally:
        route_patch.stop()

    assert response.status_code == 502
    assert "error" in response.data


def test_unassessed_request_preserves_existing_behavior(request_data, route_feature):
    route_patch = setup_routes(route_feature, count=1)
    try:
        response = make_request(request_data)
    finally:
        route_patch.stop()

    assert response.status_code == 200
    assert response.data["weather_assessed"] is False
    assert response.data["recommended_route_id"] is None
    assert "risk_summary" not in response.data["routes"][0]
