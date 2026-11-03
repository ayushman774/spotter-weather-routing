
import pytest

from routing.services.risk import (
    RiskLevel,
    WeatherConditions,
    assess_weather_risk,
    classify_rain,
    classify_snow,
    classify_wind,
)


@pytest.mark.parametrize(
    ("wind_mph", "expected"),
    [
        (0, RiskLevel.LOW),
        (24.9, RiskLevel.LOW),
        (25, RiskLevel.MODERATE),
        (34.9, RiskLevel.MODERATE),
        (35, RiskLevel.HIGH),
        (44.9, RiskLevel.HIGH),
        (45, RiskLevel.SEVERE),
        (54.9, RiskLevel.SEVERE),
        (55, RiskLevel.NO_TRAVEL),
    ],
)
def test_wind_thresholds(wind_mph, expected):
    assert classify_wind(wind_mph) == expected


@pytest.mark.parametrize(
    ("rain", "expected"),
    [
        (0.09, RiskLevel.LOW),
        (0.10, RiskLevel.MODERATE),
        (0.25, RiskLevel.HIGH),
        (0.50, RiskLevel.SEVERE),
        (1.00, RiskLevel.SEVERE),
        (1.01, RiskLevel.NO_TRAVEL),
    ],
)
def test_rain_thresholds(rain, expected):
    assert classify_rain(rain) == expected


@pytest.mark.parametrize(
    ("snow", "expected"),
    [
        (0.49, RiskLevel.LOW),
        (0.50, RiskLevel.MODERATE),
        (1.00, RiskLevel.HIGH),
        (2.00, RiskLevel.SEVERE),
        (3.00, RiskLevel.SEVERE),
        (3.01, RiskLevel.NO_TRAVEL),
    ],
)
def test_snow_thresholds(snow, expected):
    assert classify_snow(snow) == expected


@pytest.mark.parametrize(
    ("wind", "load", "expected"),
    [
        (40, 40_000, RiskLevel.HIGH),
        (40, 40_001, RiskLevel.SEVERE),
        (45, 30_000, RiskLevel.SEVERE),
        (45, 30_001, RiskLevel.NO_TRAVEL),
        (55, 0, RiskLevel.NO_TRAVEL),
    ],
)
def test_load_adjusted_wind_risk(wind, load, expected):
    weather = WeatherConditions(wind, 0, 0)

    result = assess_weather_risk(weather, load)

    assert result.level == expected
    assert result.wind_risk == expected


def test_highest_weather_risk_wins():
    weather = WeatherConditions(
        wind_mph=20,
        rain_in_per_hr=0.3,
        snow_in_per_hr=2.5,
    )

    result = assess_weather_risk(weather, 20_000)

    assert result.level == RiskLevel.SEVERE
    assert result.rain_risk == RiskLevel.HIGH
    assert result.snow_risk == RiskLevel.SEVERE


def test_invalid_measurements_are_rejected():
    weather = WeatherConditions(-10, 0, 0)

    with pytest.raises(ValueError):
        assess_weather_risk(weather, 20_000)


def test_non_finite_measurements_are_rejected():
    weather = WeatherConditions(float("nan"), 0, 0)

    with pytest.raises(ValueError):
        assess_weather_risk(weather, 20_000)
