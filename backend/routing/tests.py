from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from routing.services.openrouteservice import Location, RoutingProviderError


class RoutingApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.payload = {
            "origin": "Denver, Colorado",
            "destination": "Colorado Springs, Colorado",
            "departure_time": "2026-11-04T12:00:00-07:00",
            "load_weight_lb": 18000,
            "checkpoint_interval_miles": 25,
            "assess_weather": False,
        }

    def test_health(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "healthy")

    def test_rejects_same_origin(self):
        self.payload["destination"] = self.payload["origin"]
        response = self.client.post("/api/routes/plan/", self.payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_rejects_invalid_interval(self):
        self.payload["checkpoint_interval_miles"] = 13
        response = self.client.post("/api/routes/plan/", self.payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_rejects_negative_weight(self):
        self.payload["load_weight_lb"] = -10
        response = self.client.post("/api/routes/plan/", self.payload, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("routing.views.OpenRouteServiceClient")
    def test_route_response(self, provider_class):
        provider = provider_class.return_value
        provider.geocode.side_effect = [
            Location("Denver", -104.9903, 39.7392),
            Location("Colorado Springs", -104.8214, 38.8339),
        ]
        provider.get_routes.return_value = [{
            "properties": {"summary": {"distance": 120000, "duration": 5400}},
            "geometry": {"type": "LineString", "coordinates": [
                [-104.9903, 39.7392], [-104.8214, 38.8339],
            ]},
        }]
        response = self.client.post("/api/routes/plan/", self.payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route_count"], 1)
        self.assertFalse(response.data["all_requested_routes_available"])
        self.assertGreaterEqual(len(response.data["routes"][0]["checkpoints"]), 2)

    @patch("routing.views.OpenRouteServiceClient")
    def test_routing_provider_failure(self, provider_class):
        provider_class.return_value.geocode.side_effect = RoutingProviderError("Unavailable")
        response = self.client.post("/api/routes/plan/", self.payload, format="json")
        self.assertEqual(response.status_code, 502)
