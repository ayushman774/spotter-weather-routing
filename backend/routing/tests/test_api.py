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


class WeatherRiskRegressionTests(SimpleTestCase):
    """Deterministic hazardous-weather tests; never call live forecast providers."""

    def test_wind_threshold_boundaries(self):
        from routing.services.risk import RiskLevel, classify_wind

        for speed, expected in (
            (24.99, RiskLevel.LOW),
            (25, RiskLevel.MODERATE),
            (35, RiskLevel.HIGH),
            (45, RiskLevel.SEVERE),
            (55, RiskLevel.NO_TRAVEL),
        ):
            with self.subTest(speed=speed):
                self.assertEqual(classify_wind(speed), expected)

    def test_rain_threshold_boundaries(self):
        from routing.services.risk import RiskLevel, classify_rain

        for rate, expected in (
            (0.09, RiskLevel.LOW),
            (0.10, RiskLevel.MODERATE),
            (0.25, RiskLevel.HIGH),
            (0.50, RiskLevel.SEVERE),
            (1.0, RiskLevel.SEVERE),
            (1.01, RiskLevel.NO_TRAVEL),
        ):
            with self.subTest(rate=rate):
                self.assertEqual(classify_rain(rate), expected)

    def test_snow_threshold_boundaries(self):
        from routing.services.risk import RiskLevel, classify_snow

        for rate, expected in (
            (0.49, RiskLevel.LOW),
            (0.50, RiskLevel.MODERATE),
            (1.0, RiskLevel.HIGH),
            (2.0, RiskLevel.SEVERE),
            (3.0, RiskLevel.SEVERE),
            (3.01, RiskLevel.NO_TRAVEL),
        ):
            with self.subTest(rate=rate):
                self.assertEqual(classify_snow(rate), expected)

    def test_heavy_load_wind_escalation(self):
        from routing.services.risk import (
            RiskLevel, WeatherConditions, assess_weather_risk,
        )

        windy = WeatherConditions(45, 0, 0)
        self.assertEqual(assess_weather_risk(windy, 30000).level, RiskLevel.SEVERE)
        assessed = assess_weather_risk(windy, 30001)
        self.assertEqual(assessed.level, RiskLevel.NO_TRAVEL)
        self.assertTrue(assessed.reasons)

        high_wind = WeatherConditions(35, 0, 0)
        self.assertEqual(assess_weather_risk(high_wind, 40000).level, RiskLevel.HIGH)
        self.assertEqual(assess_weather_risk(high_wind, 40001).level, RiskLevel.SEVERE)

    def test_combined_hazards_use_highest_risk(self):
        from routing.services.risk import (
            RiskLevel, WeatherConditions, assess_weather_risk,
        )

        assessment = assess_weather_risk(
            WeatherConditions(wind_mph=36, rain_in_per_hr=0.6, snow_in_per_hr=0.5),
            load_weight_lb=18000,
        )
        self.assertEqual(assessment.wind_risk, RiskLevel.HIGH)
        self.assertEqual(assessment.rain_risk, RiskLevel.SEVERE)
        self.assertEqual(assessment.snow_risk, RiskLevel.MODERATE)
        self.assertEqual(assessment.level, RiskLevel.SEVERE)

    def test_invalid_weather_never_defaults_to_low(self):
        from routing.services.risk import WeatherConditions, assess_weather_risk

        for conditions in (
            WeatherConditions(float("nan"), 0, 0),
            WeatherConditions(float("inf"), 0, 0),
            WeatherConditions(0, -0.1, 0),
            WeatherConditions(0, 0, -1),
        ):
            with self.subTest(conditions=conditions):
                with self.assertRaises(ValueError):
                    assess_weather_risk(conditions, 40000)

    def test_checkpoint_exposure_and_risk_summary(self):
        from datetime import datetime, timezone

        from routing.services.risk import WeatherConditions
        from routing.services.route_scoring import assess_route
        from routing.services.weather import CheckpointForecast

        conditions = [
            WeatherConditions(5, 0, 0),
            WeatherConditions(36, 0, 0),
            WeatherConditions(55, 0, 0),
        ]
        checkpoints = [
            {
                "latitude": 41.0,
                "longitude": -105.0 + i,
                "eta": "2026-11-04T12:00:00+00:00",
                "distance_miles": float(i * 10),
            }
            for i in range(3)
        ]
        provider = Mock()
        provider.get_forecast.side_effect = [
            CheckpointForecast(
                requested_eta=datetime(2026, 11, 4, 12, tzinfo=timezone.utc).isoformat(),
                forecast_time=datetime(2026, 11, 4, 12, tzinfo=timezone.utc).isoformat(),
                conditions=condition,
            )
            for condition in conditions
        ]
        enriched, summary = assess_route(checkpoints, 18000, weather_client=provider)
        self.assertEqual([cp["risk"]["level"] for cp in enriched],
                         ["LOW", "HIGH", "NO_TRAVEL"])
        self.assertEqual([cp["represented_miles"] for cp in enriched],
                         [5.0, 10.0, 5.0])
        self.assertEqual(summary.high_miles, 10.0)
        self.assertEqual(summary.severe_miles, 5.0)
        self.assertEqual(summary.no_travel_miles, 5.0)
        self.assertAlmostEqual(summary.average_risk, 2.0)
        self.assertEqual(provider.get_forecast.call_count, 3)

    def test_weather_provider_failure_is_not_silently_ignored(self):
        from routing.services.route_scoring import assess_route
        from routing.services.weather import WeatherProviderError

        checkpoints = [
            {"latitude": 41.0, "longitude": -105.0,
             "eta": "2026-11-04T12:00:00+00:00", "distance_miles": 0.0},
            {"latitude": 42.0, "longitude": -104.0,
             "eta": "2026-11-04T13:00:00+00:00", "distance_miles": 10.0},
        ]
        provider = Mock()
        provider.get_forecast.side_effect = WeatherProviderError("Forecast unavailable")
        with self.assertRaises(WeatherProviderError):
            assess_route(checkpoints, 40000, weather_client=provider)

    def test_ranking_prefers_safe_route_over_faster_hazardous_route(self):
        from routing.services.route_scoring import rank_routes

        safe = {
            "id": "safe", "duration_minutes": 180,
            "risk_summary": {"no_travel_miles": 0, "severe_miles": 0,
                             "high_miles": 0, "average_risk": 0},
        }
        severe = {
            "id": "severe", "duration_minutes": 60,
            "risk_summary": {"no_travel_miles": 0, "severe_miles": 20,
                             "high_miles": 0, "average_risk": 3},
        }
        no_travel = {
            "id": "no-travel", "duration_minutes": 30,
            "risk_summary": {"no_travel_miles": 10, "severe_miles": 10,
                             "high_miles": 0, "average_risk": 4},
        }
        self.assertEqual(
            [route["id"] for route in rank_routes([no_travel, severe, safe])],
            ["safe", "severe", "no-travel"],
        )


class WeatherProviderResilienceTests(SimpleTestCase):
    @staticmethod
    def checkpoint():
        return {
            "latitude": 42.0,
            "longitude": -78.0,
            "eta": "2026-11-04T12:00:00+00:00",
        }

    @staticmethod
    def forecast_payload(winds=None):
        return {
            "hourly": {
                "time": [
                    "2026-11-04T11:00",
                    "2026-11-04T12:00",
                    "2026-11-04T13:00",
                ],
                "wind_speed_10m": winds if winds is not None else [5, 40, 7],
                "rain": [0, 0.3, 0],
                "snowfall": [0, 0, 0],
            }
        }

    def test_missing_unrelated_hour_does_not_discard_valid_checkpoint(self):
        from datetime import datetime
        from routing.services.weather import OpenMeteoClient

        payload = self.forecast_payload(winds=[None, 40, 7])
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )
        client = OpenMeteoClient(transport=transport)
        checkpoint = self.checkpoint()
        forecast = client.get_forecast(
            checkpoint["latitude"],
            checkpoint["longitude"],
            datetime.fromisoformat(checkpoint["eta"]),
        )
        self.assertEqual(forecast.conditions.wind_mph, 40)

    def test_missing_checkpoint_hour_is_not_treated_as_safe(self):
        from datetime import datetime
        from routing.services.weather import OpenMeteoClient, WeatherProviderError

        payload = self.forecast_payload(winds=[5, None, 7])
        client = OpenMeteoClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=payload)
            )
        )
        checkpoint = self.checkpoint()
        with self.assertRaises(WeatherProviderError):
            client.get_forecast(
                checkpoint["latitude"],
                checkpoint["longitude"],
                datetime.fromisoformat(checkpoint["eta"]),
            )

    def test_transient_503_retries_and_recovers(self):
        from routing.services.weather import OpenMeteoClient

        calls = []

        def respond(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(503, json={"error": "temporary"})
            return httpx.Response(200, json=self.forecast_payload())

        client = OpenMeteoClient(transport=httpx.MockTransport(respond))
        client.prefetch([self.checkpoint()])
        self.assertEqual(len(calls), 2)

    def test_non_retryable_403_fails_immediately(self):
        from routing.services.weather import OpenMeteoClient, WeatherProviderError

        calls = []

        def respond(request):
            calls.append(request)
            return httpx.Response(403, json={"error": "forbidden"})

        client = OpenMeteoClient(transport=httpx.MockTransport(respond))
        with self.assertRaises(WeatherProviderError):
            client.prefetch([self.checkpoint()])
        self.assertEqual(len(calls), 1)


class GeocodingDiagnosticsTests(SimpleTestCase):
    def test_geocoding_http_429_logs_status_without_secrets(self):
        from routing.services.openrouteservice import (
            OpenRouteServiceClient, RoutingProviderError,
        )

        client = OpenRouteServiceClient(api_key="test-secret-key")
        with patch(
            "routing.services.openrouteservice.httpx.get",
            return_value=httpx.Response(
                429,
                request=httpx.Request(
                    "GET", "https://api.openrouteservice.org/geocode/search"
                ),
            ),
        ):
            with self.assertLogs("routing.services.openrouteservice", level="WARNING") as logs:
                with self.assertRaises(RoutingProviderError):
                    client.geocode("Denver")
        output = "\\n".join(logs.output)
        self.assertIn("status=429", output)
        self.assertNotIn("test-secret-key", output)
        self.assertNotIn("Denver", output)

    def test_geocoding_connection_failure_logs_exception_type(self):
        from routing.services.openrouteservice import (
            OpenRouteServiceClient, RoutingProviderError,
        )

        client = OpenRouteServiceClient(api_key="test-secret-key")
        with patch(
            "routing.services.openrouteservice.httpx.get",
            side_effect=httpx.ConnectError("connection failed"),
        ):
            with self.assertLogs("routing.services.openrouteservice", level="WARNING") as logs:
                with self.assertRaises(RoutingProviderError):
                    client.geocode("Denver")
        self.assertIn("type=ConnectError", "\\n".join(logs.output))
