"""Open-Meteo hourly forecast adapter for route checkpoint risk assessment."""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite

import httpx

from routing.services.risk import WeatherConditions

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CM_PER_INCH = 2.54


class WeatherProviderError(Exception):
    """Forecast data could not be retrieved or safely interpreted."""


@dataclass(frozen=True)
class CheckpointForecast:
    requested_eta: str
    forecast_time: str
    conditions: WeatherConditions


class OpenMeteoClient:
    """Read hourly forecast data; fail closed if required measurements are absent."""

    def __init__(self, transport: httpx.BaseTransport | None = None):
        self.transport = transport

    def get_forecast(
        self, latitude: float, longitude: float, eta: datetime
    ) -> CheckpointForecast:
        if eta.tzinfo is None or eta.utcoffset() is None:
            raise ValueError("Checkpoint ETA must include a timezone.")
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("Invalid checkpoint coordinates.")

        target = eta.astimezone(timezone.utc)
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "wind_speed_10m,rain,snowfall",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "UTC",
            "forecast_days": 3,
        }

        try:
            with httpx.Client(timeout=15, transport=self.transport) as client:
                response = client.get(FORECAST_URL, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WeatherProviderError("Weather forecast request failed.") from exc

        hourly = payload.get("hourly")
        if not isinstance(hourly, dict):
            raise WeatherProviderError("Missing hourly forecast data.")

        try:
            times = hourly["time"]
            winds = hourly["wind_speed_10m"]
            rains = hourly["rain"]
            snows = hourly["snowfall"]
            if not times or not (
                len(times) == len(winds) == len(rains) == len(snows)
            ):
                raise ValueError("Hourly forecast arrays are incomplete.")

            parsed_times = [
                datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                for value in times
            ]
            parsed_times = [
                value.replace(tzinfo=timezone.utc)
                if value.tzinfo is None
                else value.astimezone(timezone.utc)
                for value in parsed_times
            ]
            index = min(
                range(len(parsed_times)),
                key=lambda i: abs((parsed_times[i] - target).total_seconds()),
            )
            # Hourly values should not be used for dates outside forecast coverage.
            if abs((parsed_times[index] - target).total_seconds()) > 1800:
                raise ValueError("ETA is outside available hourly forecast coverage.")

            wind = float(winds[index])
            rain = float(rains[index])
            snow = float(snows[index]) / CM_PER_INCH
            if any(not isfinite(v) or v < 0 for v in (wind, rain, snow)):
                raise ValueError("Invalid forecast measurement.")
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise WeatherProviderError("Forecast data unavailable for checkpoint ETA.") from exc

        return CheckpointForecast(
            requested_eta=target.isoformat(),
            forecast_time=parsed_times[index].isoformat(),
            conditions=WeatherConditions(
                wind_mph=wind,
                rain_in_per_hr=rain,
                snow_in_per_hr=snow,
            ),
        )
