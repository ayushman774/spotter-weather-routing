
import os
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.openrouteservice.org"


class RoutingProviderError(Exception):
    """Raised when the external routing service fails."""


@dataclass(frozen=True)
class Location:
    name: str
    longitude: float
    latitude: float


class OpenRouteServiceClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("ORS_API_KEY")

        if not self.api_key:
            raise RoutingProviderError(
                "ORS_API_KEY is not configured."
            )

    def geocode(self, place: str) -> Location:
        try:
            response = httpx.get(
                f"{BASE_URL}/geocode/search",
                params={
                    "api_key": self.api_key,
                    "text": place,
                    "size": 1,
                },
                timeout=15,
            )
            response.raise_for_status()
            features = response.json().get("features", [])

        except (httpx.HTTPError, ValueError) as exc:
            raise RoutingProviderError(
                "Unable to geocode the requested location."
            ) from exc

        if not features:
            raise RoutingProviderError(
                f"No location found for '{place}'."
            )

        feature = features[0]
        longitude, latitude = feature["geometry"]["coordinates"]

        return Location(
            name=feature["properties"].get("label", place),
            longitude=longitude,
            latitude=latitude,
        )

    def get_routes(
        self,
        origin: Location,
        destination: Location,
    ) -> list[dict]:
        payload = {
            "coordinates": [
                [origin.longitude, origin.latitude],
                [destination.longitude, destination.latitude],
            ],
            "alternative_routes": {
                "target_count": 3,
                "share_factor": 0.6,
                "weight_factor": 1.4,
            },
        }

        try:
            response = httpx.post(
                f"{BASE_URL}/v2/directions/driving-hgv/geojson",
                headers={
                    "Authorization": self.api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            features = response.json().get("features", [])

        except httpx.HTTPStatusError as exc:
            raise RoutingProviderError(
                f"Routing provider rejected the request "
                f"(HTTP {exc.response.status_code})."
            ) from exc

        except (httpx.HTTPError, ValueError) as exc:
            raise RoutingProviderError(
                "Unable to retrieve routes from the provider."
            ) from exc

        if not features:
            raise RoutingProviderError(
                "No drivable routes were returned."
            )

        return features
