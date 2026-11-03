
from dataclasses import dataclass
from enum import IntEnum
from math import isfinite


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


@dataclass(frozen=True)
class WeatherConditions:
    wind_mph: float
    rain_in_per_hr: float
    snow_in_per_hr: float


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    wind_risk: RiskLevel
    rain_risk: RiskLevel
    snow_risk: RiskLevel
    reasons: tuple[str, ...]


def classify_wind(wind_mph: float) -> RiskLevel:
    if wind_mph >= 55:
        return RiskLevel.NO_TRAVEL
    if wind_mph >= 45:
        return RiskLevel.SEVERE
    if wind_mph >= 35:
        return RiskLevel.HIGH
    if wind_mph >= 25:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_rain(rain_in_per_hr: float) -> RiskLevel:
    if rain_in_per_hr > 1.0:
        return RiskLevel.NO_TRAVEL
    if rain_in_per_hr >= 0.5:
        return RiskLevel.SEVERE
    if rain_in_per_hr >= 0.25:
        return RiskLevel.HIGH
    if rain_in_per_hr >= 0.10:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_snow(snow_in_per_hr: float) -> RiskLevel:
    if snow_in_per_hr > 3.0:
        return RiskLevel.NO_TRAVEL
    if snow_in_per_hr >= 2.0:
        return RiskLevel.SEVERE
    if snow_in_per_hr >= 1.0:
        return RiskLevel.HIGH
    if snow_in_per_hr >= 0.5:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def assess_weather_risk(
    weather: WeatherConditions,
    load_weight_lb: float,
) -> RiskAssessment:
    measurements = (
        weather.wind_mph,
        weather.rain_in_per_hr,
        weather.snow_in_per_hr,
        load_weight_lb,
    )

    if any(not isfinite(value) or value < 0 for value in measurements):
        raise ValueError("Weather measurements and load weight must be finite and non-negative.")

    wind_risk = classify_wind(weather.wind_mph)
    rain_risk = classify_rain(weather.rain_in_per_hr)
    snow_risk = classify_snow(weather.snow_in_per_hr)

    reasons = []

    if weather.wind_mph >= 55:
        reasons.append("Wind speed is at or above the no-travel threshold.")
    elif weather.wind_mph >= 45 and load_weight_lb > 30_000:
        wind_risk = RiskLevel.NO_TRAVEL
        reasons.append("Wind exceeds the safe limit for loads above 30,000 lb.")
    elif weather.wind_mph >= 35 and load_weight_lb > 40_000:
        wind_risk = max(wind_risk, RiskLevel.SEVERE)
        reasons.append("High wind increases risk for loads above 40,000 lb.")

    if rain_risk == RiskLevel.NO_TRAVEL:
        reasons.append("Rainfall exceeds the no-travel threshold.")

    if snow_risk == RiskLevel.NO_TRAVEL:
        reasons.append("Snowfall exceeds the no-travel threshold.")

    overall_risk = max(wind_risk, rain_risk, snow_risk)

    return RiskAssessment(
        level=overall_risk,
        wind_risk=wind_risk,
        rain_risk=rain_risk,
        snow_risk=snow_risk,
        reasons=tuple(reasons),
    )
