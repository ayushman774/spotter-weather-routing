"""Deterministic tests for checkpoint exposure and route ranking."""

from dataclasses import dataclass

import pytest

from routing.services.risk import WeatherConditions
from routing.services.route_scoring import assess_route, rank_routes


@dataclass
class FakeForecast:
    forecast_time: str
    conditions: WeatherConditions


class FakeWeather:
    def __init__(self, winds):
        self.winds = iter(winds)

    def get_forecast(self, latitude, longitude, eta):
        return FakeForecast(
            eta.isoformat(),
            WeatherConditions(next(self.winds), 0, 0),
        )


def checkpoints(distances=(0, 25, 50, 60)):
    return [
        {
            "latitude": 39.0,
            "longitude": -105.0,
            "distance_miles": distance,
            "eta": "2026-11-04T15:00:00+00:00",
        }
        for distance in distances
    ]


def test_distance_weighted_severe_and_high_miles():
    samples, summary = assess_route(
        checkpoints(), 25000, FakeWeather([20, 45, 35, 20])
    )
    # At 25 mi: 25 represented miles; at 50 mi: 17.5 represented miles.
    assert summary.severe_miles == pytest.approx(25)
    assert summary.high_miles == pytest.approx(17.5)
    assert summary.no_travel_miles == 0
    assert samples[1]["risk"]["level"] == "SEVERE"
    assert sum(s["represented_miles"] for s in samples) == pytest.approx(60)


def test_load_adjustment_marks_no_travel():
    _, summary = assess_route(
        checkpoints((0, 25)), 35000, FakeWeather([45, 45])
    )
    assert summary.no_travel_miles == pytest.approx(25)
    assert summary.severe_miles == pytest.approx(25)


def test_ranking_prefers_less_severe_over_faster_time():
    routes = [
        {
            "id": "fast",
            "duration_minutes": 80,
            "risk_summary": {"severe_miles": 10, "high_miles": 0, "average_risk": 1},
        },
        {
            "id": "safe",
            "duration_minutes": 110,
            "risk_summary": {"severe_miles": 0, "high_miles": 0, "average_risk": 1},
        },
    ]
    assert rank_routes(routes)[0]["id"] == "safe"


def test_ranking_tie_breaks_by_high_then_average_then_duration():
    routes = [
        {"id": "a", "duration_minutes": 80, "risk_summary": {
            "severe_miles": 0, "high_miles": 10, "average_risk": 0.5}},
        {"id": "b", "duration_minutes": 110, "risk_summary": {
            "severe_miles": 0, "high_miles": 0, "average_risk": 0.8}},
        {"id": "c", "duration_minutes": 120, "risk_summary": {
            "severe_miles": 0, "high_miles": 0, "average_risk": 0.3}},
    ]
    assert [r["id"] for r in rank_routes(routes)] == ["c", "b", "a"]


def test_rejects_non_monotonic_checkpoints():
    with pytest.raises(ValueError):
        assess_route(checkpoints((0, 25, 25)), 0, FakeWeather([0, 0, 0]))
