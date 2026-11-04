from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite

import httpx

from routing.services.risk import WeatherConditions

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CM_PER_INCH = 2.54
MAX_CACHE_ENTRIES = 2048
MAX_FORECAST_DAYS = 16
BATCH_SIZE = 25


class WeatherProviderError(Exception):
    pass


@dataclass(frozen=True)
class CheckpointForecast:
    requested_eta: str
    forecast_time: str
    conditions: WeatherConditions


class OpenMeteoClient:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        self.transport = transport
        self._cache = OrderedDict()

    @staticmethod
    def _coordinates(latitude, longitude):
        latitude = float(latitude)
        longitude = float(longitude)
        if not (
            isfinite(latitude)
            and isfinite(longitude)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            raise ValueError("Invalid checkpoint coordinates.")
        return latitude, longitude

    @staticmethod
    def _target(eta):
        if eta.tzinfo is None or eta.utcoffset() is None:
            raise ValueError("Checkpoint ETA must include a timezone.")
        return eta.astimezone(timezone.utc)

    @staticmethod
    def _parse_hourly(payload):
        if not isinstance(payload, dict):
            raise WeatherProviderError("Missing hourly forecast data.")
        hourly = payload.get("hourly")
        if not isinstance(hourly, dict):
            raise WeatherProviderError("Missing hourly forecast data.")
        try:
            times = hourly["time"]
            winds = hourly["wind_speed_10m"]
            rains = hourly["rain"]
            snows = hourly["snowfall"]
            if (
                not isinstance(times, list)
                or not all(isinstance(values, list) for values in (winds, rains, snows))
                or not times
                or not (len(times) == len(winds) == len(rains) == len(snows))
            ):
                raise ValueError("Invalid hourly forecast arrays.")
            parsed = []
            for index, value in enumerate(times):
                moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                moment = (
                    moment.replace(tzinfo=timezone.utc)
                    if moment.tzinfo is None
                    else moment.astimezone(timezone.utc)
                )
                wind = float(winds[index])
                rain = float(rains[index])
                snow = float(snows[index]) / CM_PER_INCH
                if any(not isfinite(v) or v < 0 for v in (wind, rain, snow)):
                    raise ValueError("Invalid forecast measurement.")
                parsed.append((moment, WeatherConditions(wind, rain, snow)))
            return parsed
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise WeatherProviderError("Forecast data unavailable for checkpoint ETA.") from exc

    def _store(self, coordinates, hourly):
        self._cache[coordinates] = hourly
        self._cache.move_to_end(coordinates)
        while len(self._cache) > MAX_CACHE_ENTRIES:
            self._cache.popitem(last=False)

    def prefetch(self, checkpoints):
        coordinates = []
        seen = set()
        latest_eta = None
        for checkpoint in checkpoints:
            key = self._coordinates(checkpoint["latitude"], checkpoint["longitude"])
            target = self._target(datetime.fromisoformat(checkpoint["eta"]))
            if latest_eta is None or target > latest_eta:
                latest_eta = target
            if key not in self._cache and key not in seen:
                coordinates.append(key)
                seen.add(key)

        # Open-Meteo forecast_days counts UTC calendar days, including today.
        today = datetime.now(timezone.utc).date()
        days = (latest_eta.date() - today).days + 1 if latest_eta else 1
        if days < 1 or days > MAX_FORECAST_DAYS:
            raise WeatherProviderError(
                "Checkpoint arrival is outside the available 16-day weather forecast window."
            )

        for start in range(0, len(coordinates), BATCH_SIZE):
            batch = coordinates[start:start + BATCH_SIZE]
            params = {
                "latitude": ",".join(str(lat) for lat, _ in batch),
                "longitude": ",".join(str(lon) for _, lon in batch),
                "hourly": "wind_speed_10m,rain,snowfall",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "UTC",
                "forecast_days": max(3, days),
            }
            try:
                with httpx.Client(timeout=15, transport=self.transport) as client:
                    response = client.get(FORECAST_URL, params=params)
                    response.raise_for_status()
                    payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise WeatherProviderError("Weather forecast request failed.") from exc

            if len(batch) == 1:
                if not isinstance(payload, dict):
                    raise WeatherProviderError("Invalid single-location forecast response.")
                payloads = [payload]
            else:
                if not isinstance(payload, list) or len(payload) != len(batch):
                    raise WeatherProviderError("Invalid multi-location forecast response.")
                payloads = payload

            parsed = [self._parse_hourly(item) for item in payloads]
            for key, hourly in zip(batch, parsed):
                self._store(key, hourly)

    def get_forecast(self, latitude, longitude, eta):
        key = self._coordinates(latitude, longitude)
        target = self._target(eta)
        if key not in self._cache:
            self.prefetch([{
                "latitude": key[0],
                "longitude": key[1],
                "eta": eta.isoformat(),
            }])
        self._cache.move_to_end(key)
        hourly = self._cache[key]
        index = min(
            range(len(hourly)),
            key=lambda i: abs((hourly[i][0] - target).total_seconds()),
        )
        forecast_time, conditions = hourly[index]
        if abs((forecast_time - target).total_seconds()) > 1800:
            # Cached forecasts may have been fetched for an earlier journey.
            # Refresh with the requested ETA before declaring the forecast unavailable.
            self._cache.pop(key, None)
            self.prefetch([{"latitude": key[0], "longitude": key[1], "eta": eta.isoformat()}])
            hourly = self._cache[key]
            index = min(range(len(hourly)), key=lambda i: abs((hourly[i][0] - target).total_seconds()))
            forecast_time, conditions = hourly[index]
            if abs((forecast_time - target).total_seconds()) > 1800:
                raise WeatherProviderError("Forecast data unavailable for checkpoint ETA.")
        return CheckpointForecast(
            requested_eta=target.isoformat(),
            forecast_time=forecast_time.isoformat(),
            conditions=conditions,
        )
