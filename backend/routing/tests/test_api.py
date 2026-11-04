from unittest.mock import Mock, patch

import httpx

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from routing.services.openrouteservice import Location, OpenRouteServiceClient, RoutingProviderError


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


class RouteRankingTests(SimpleTestCase):
    def test_safer_route_ranks_before_shorter_no_travel_route(self):
        from routing.services.route_scoring import rank_routes

        unsafe = {
            "id": "unsafe", "duration_minutes": 40,
            "risk_summary": {
                "no_travel_miles": 1, "severe_miles": 1,
                "high_miles": 0, "average_risk": 1,
            },
        }
        safer = {
            "id": "safer", "duration_minutes": 70,
            "risk_summary": {
                "no_travel_miles": 0, "severe_miles": 0,
                "high_miles": 0, "average_risk": 0,
            },
        }
        self.assertEqual(rank_routes([unsafe, safer])[0]["id"], "safer")


class OpenRouteServiceFallbackTests(SimpleTestCase):
    def setUp(self):
        self.client = OpenRouteServiceClient(api_key="test-key")
        self.origin = Location("Chicago", -87.6298, 41.8781)
        self.destination = Location("Minneapolis", -93.2650, 44.9778)

    @staticmethod
    def provider_response(status_code, body=None):
        request = httpx.Request("POST", "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson")
        return httpx.Response(status_code, request=request, json=body or {})

    @patch("routing.services.openrouteservice.httpx.post")
    def test_retries_without_alternatives_after_400(self, post):
        successful = self.provider_response(200, {"features": [{"id": "single-hgv-route"}]})
        post.side_effect = [self.provider_response(400), successful]
        routes = self.client.get_routes(self.origin, self.destination)
        self.assertEqual(routes, [{"id": "single-hgv-route"}])
        self.assertEqual(post.call_count, 2)
        self.assertIn("alternative_routes", post.call_args_list[0].kwargs["json"])
        self.assertNotIn("alternative_routes", post.call_args_list[1].kwargs["json"])
        self.assertEqual(
            post.call_args_list[1].kwargs["json"]["coordinates"],
            [[-87.6298, 41.8781], [-93.265, 44.9778]],
        )

    @patch("routing.services.openrouteservice.httpx.post")
    def test_does_not_retry_other_provider_errors(self, post):
        post.return_value = self.provider_response(403)
        with self.assertRaisesRegex(RoutingProviderError, "HTTP 403"):
            self.client.get_routes(self.origin, self.destination)
        self.assertEqual(post.call_count, 1)

    @patch("routing.services.openrouteservice.httpx.post")
    def test_second_400_is_reported_without_more_retries(self, post):
        post.return_value = self.provider_response(400)
        with self.assertRaisesRegex(RoutingProviderError, "HTTP 400"):
            self.client.get_routes(self.origin, self.destination)
        self.assertEqual(post.call_count, 2)

    @patch("routing.services.openrouteservice.httpx.post")
    def test_successful_alternatives_do_not_retry(self, post):
        post.return_value = self.provider_response(200, {"features": [{"id": "alternative"}]})
        self.assertEqual(len(self.client.get_routes(self.origin, self.destination)), 1)
        self.assertEqual(post.call_count, 1)
