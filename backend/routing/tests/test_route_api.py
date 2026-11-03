
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from rest_framework.test import APIRequestFactory

from routing.services.openrouteservice import (
    Location,
    RoutingProviderError,
)
from routing.views import plan_routes


@pytest.fixture
def request_data():
    return {
        "origin": "Denver, Colorado, USA",
        "destination": "Colorado Springs, Colorado, USA",
        "departure_time": "2026-11-04T08:00:00-07:00",
        "load_weight_lb": 25000,
        "checkpoint_interval_miles": 25,
    }


@pytest.fixture
def route_feature():
    return {
        "type": "Feature",
        "properties": {
            "summary": {
                "distance": 100000,
                "duration": 5400,
            },
        },
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [-104.98, 39.74],
                [-104.90, 39.30],
                [-104.81, 38.87],
            ],
        },
    }


def make_request(data):
    request = APIRequestFactory().post(
        "/api/routes/plan/",
        data,
        format="json",
    )
    return plan_routes(request)


@pytest.mark.parametrize("route_count", [1, 2, 3])
def test_route_count_is_reported_accurately(
    request_data, route_feature, route_count
):
    with patch(
        "routing.views.OpenRouteServiceClient"
    ) as client_class:
        client = client_class.return_value

        client.geocode.side_effect = [
            Location("Denver", -104.98, 39.74),
            Location("Colorado Springs", -104.81, 38.87),
        ]

        client.get_routes.return_value = [
            route_feature for _ in range(route_count)
        ]

        response = make_request(request_data)

    assert response.status_code == 200
    assert response.data["route_count"] == route_count
    assert response.data["requested_route_count"] == 3
    assert (
        response.data["all_requested_routes_available"]
        is (route_count == 3)
    )
    assert len(response.data["routes"]) == route_count

    for route in response.data["routes"]:
        assert route["checkpoints"]
        assert route["geometry"]["type"] == "LineString"
        assert route["distance_miles"] > 0
        assert route["duration_minutes"] > 0


def test_invalid_checkpoint_interval_returns_400(request_data):
    request_data["checkpoint_interval_miles"] = 15

    response = make_request(request_data)

    assert response.status_code == 400


def test_same_origin_and_destination_returns_400(request_data):
    request_data["destination"] = request_data["origin"]

    response = make_request(request_data)

    assert response.status_code == 400


def test_provider_failure_returns_502(request_data):
    with patch(
        "routing.views.OpenRouteServiceClient"
    ) as client_class:
        client_class.return_value.geocode.side_effect = (
            RoutingProviderError("Provider unavailable")
        )

        response = make_request(request_data)

    assert response.status_code == 502
    assert "error" in response.data


def test_checkpoint_etas_are_timezone_aware(
    request_data, route_feature
):
    with patch(
        "routing.views.OpenRouteServiceClient"
    ) as client_class:
        client = client_class.return_value

        client.geocode.side_effect = [
            Location("Denver", -104.98, 39.74),
            Location("Colorado Springs", -104.81, 38.87),
        ]
        client.get_routes.return_value = [route_feature]

        response = make_request(request_data)

    checkpoints = response.data["routes"][0]["checkpoints"]

    for checkpoint in checkpoints:
        eta = datetime.fromisoformat(checkpoint["eta"])
        assert eta.tzinfo is not None
        assert eta.utcoffset() is not None
