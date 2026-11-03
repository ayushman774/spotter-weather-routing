"""Distance-weighted checkpoint risk assessment and lexicographic route ranking."""

from dataclasses import dataclass
from datetime import datetime

from routing.services.risk import RiskLevel, assess_weather_risk
from routing.services.weather import OpenMeteoClient


@dataclass(frozen=True)
class RouteRiskSummary:
    severe_miles: float
    high_miles: float
    average_risk: float
    no_travel_miles: float

    def to_dict(self):
        return {
            "severe_miles": round(self.severe_miles, 2),
            "high_miles": round(self.high_miles, 2),
            "average_risk": round(self.average_risk, 3),
            "no_travel_miles": round(self.no_travel_miles, 2),
        }


def assess_route(checkpoints, load_weight_lb, weather_client=None):
    """Assess each checkpoint; midpoint boundary gives each sample a distance span.

    Endpoints represent half of their neighboring segment, interior samples
    represent half the preceding plus half the following segment. This avoids
    counting a single high-risk point as an entire fixed checkpoint interval.
    """
    if len(checkpoints) < 2:
        raise ValueError("At least two checkpoints are required.")

    client = weather_client if weather_client is not None else OpenMeteoClient()
    distances = [float(cp["distance_miles"]) for cp in checkpoints]
    if distances[0] != 0 or any(
        b <= a for a, b in zip(distances, distances[1:])
    ):
        raise ValueError("Checkpoint distances must increase from zero.")

    samples = []
    for i, checkpoint in enumerate(checkpoints):
        forecast = client.get_forecast(
            float(checkpoint["latitude"]),
            float(checkpoint["longitude"]),
            datetime.fromisoformat(checkpoint["eta"]),
        )
        assessment = assess_weather_risk(forecast.conditions, load_weight_lb)
        left = 0.0 if i == 0 else (distances[i - 1] + distances[i]) / 2
        right = (
            distances[-1]
            if i == len(distances) - 1
            else (distances[i] + distances[i + 1]) / 2
        )
        miles = right - left
        samples.append({
            **checkpoint,
            "weather": {
                "wind_mph": forecast.conditions.wind_mph,
                "rain_in_per_hr": forecast.conditions.rain_in_per_hr,
                "snow_in_per_hr": forecast.conditions.snow_in_per_hr,
                "forecast_time": forecast.forecast_time,
            },
            "risk": {
                "level": assessment.level.name,
                "score": int(assessment.level),
                "reasons": list(assessment.reasons),
            },
            "represented_miles": round(miles, 3),
            "_raw_miles": miles,
        })

    total = distances[-1]
    severe = sum(
        cp["_raw_miles"] for cp in samples if cp["risk"]["score"] >= RiskLevel.SEVERE
    )
    high = sum(
        cp["_raw_miles"] for cp in samples if cp["risk"]["score"] == RiskLevel.HIGH
    )
    no_travel = sum(
        cp["_raw_miles"] for cp in samples if cp["risk"]["score"] == RiskLevel.NO_TRAVEL
    )
    average = sum(
        cp["_raw_miles"] * cp["risk"]["score"] for cp in samples
    ) / total

    for cp in samples:
        del cp["_raw_miles"]

    return samples, RouteRiskSummary(severe, high, average, no_travel)


def rank_routes(routes):
    """Prefer no-travel-free routes, then less severe/high exposure and duration."""
    return sorted(
        routes,
        key=lambda route: (
            route["risk_summary"].get("no_travel_miles", 0) > 0,
            route["risk_summary"].get("no_travel_miles", 0),
            route["risk_summary"]["severe_miles"],
            route["risk_summary"]["high_miles"],
            route["risk_summary"]["average_risk"],
            route["duration_minutes"],
            route["id"],
        ),
    )
