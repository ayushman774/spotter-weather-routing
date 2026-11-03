
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt

METERS_PER_MILE = 1609.344
EARTH_RADIUS_METERS = 6_371_000


@dataclass(frozen=True)
class Checkpoint:
    latitude: float
    longitude: float
    distance_miles: float
    eta: str

    def to_dict(self) -> dict:
        return asdict(self)


def distance_meters(
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    """Calculate distance between two (longitude, latitude) points."""
    lon1, lat1 = map(radians, start)
    lon2, lat2 = map(radians, end)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        sin(dlat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    )

    return 2 * EARTH_RADIUS_METERS * asin(min(1.0, sqrt(a)))


def generate_checkpoints(
    geometry: list[list[float]],
    route_distance_meters: float,
    duration_seconds: float,
    departure_time: datetime,
    interval_miles: int = 25,
) -> list[Checkpoint]:
    """
    Place checkpoints along route geometry.

    Geometry uses GeoJSON coordinate order: [longitude, latitude].
    ETA is estimated using proportional progress along the route.
    """
    if interval_miles not in (10, 25, 50):
        raise ValueError("Checkpoint interval must be 10, 25, or 50 miles.")

    if len(geometry) < 2:
        raise ValueError("Route geometry requires at least two coordinates.")

    if route_distance_meters <= 0 or duration_seconds <= 0:
        raise ValueError("Route distance and duration must be positive.")

    if departure_time.tzinfo is None:
        raise ValueError("Departure time must include timezone information.")

    points = [tuple(point) for point in geometry]

    segment_lengths = [
        distance_meters(points[index], points[index + 1])
        for index in range(len(points) - 1)
    ]

    geometry_length = sum(segment_lengths)

    if geometry_length <= 0:
        raise ValueError("Route geometry must have nonzero length.")

    interval_meters = interval_miles * METERS_PER_MILE
    checkpoints = []

    target_distance = 0.0
    segment_index = 0
    traversed_distance = 0.0

    while target_distance < route_distance_meters:
        geometry_target = (
            target_distance / route_distance_meters
        ) * geometry_length

        while (
            segment_index < len(segment_lengths) - 1
            and traversed_distance + segment_lengths[segment_index]
            < geometry_target
        ):
            traversed_distance += segment_lengths[segment_index]
            segment_index += 1

        segment_length = segment_lengths[segment_index]

        fraction = (
            (geometry_target - traversed_distance) / segment_length
            if segment_length > 0
            else 0.0
        )

        fraction = max(0.0, min(1.0, fraction))

        start = points[segment_index]
        end = points[segment_index + 1]

        longitude = start[0] + (end[0] - start[0]) * fraction
        latitude = start[1] + (end[1] - start[1]) * fraction

        progress = target_distance / route_distance_meters
        eta = departure_time + timedelta(
            seconds=duration_seconds * progress
        )

        checkpoints.append(
            Checkpoint(
                latitude=round(latitude, 6),
                longitude=round(longitude, 6),
                distance_miles=round(
                    target_distance / METERS_PER_MILE, 2
                ),
                eta=eta.isoformat(),
            )
        )

        target_distance += interval_meters

    # Always include the destination exactly once.
    destination = points[-1]
    arrival = departure_time + timedelta(seconds=duration_seconds)

    checkpoints.append(
        Checkpoint(
            latitude=round(destination[1], 6),
            longitude=round(destination[0], 6),
            distance_miles=round(
                route_distance_meters / METERS_PER_MILE, 2
            ),
            eta=arrival.isoformat(),
        )
    )

    return checkpoints
