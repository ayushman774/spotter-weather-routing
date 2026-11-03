
from datetime import datetime, timedelta, timezone

import pytest

from routing.services.checkpoints import (
    METERS_PER_MILE,
    generate_checkpoints,
)

DEPARTURE = datetime(
    2026, 11, 4, 8, 0, tzinfo=timezone.utc
)

GEOMETRY = [
    [-100.0, 40.0],
    [-99.5, 40.0],
    [-99.0, 40.0],
]


@pytest.mark.parametrize(
    ("interval", "expected_distances"),
    [
        (10, [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]),
        (25, [0, 25, 50, 75, 100]),
        (50, [0, 50, 100]),
    ],
)
def test_checkpoint_intervals(interval, expected_distances):
    checkpoints = generate_checkpoints(
        geometry=GEOMETRY,
        route_distance_meters=100 * METERS_PER_MILE,
        duration_seconds=7200,
        departure_time=DEPARTURE,
        interval_miles=interval,
    )

    assert [
        checkpoint.distance_miles
        for checkpoint in checkpoints
    ] == expected_distances


def test_checkpoint_eta():
    checkpoints = generate_checkpoints(
        geometry=GEOMETRY,
        route_distance_meters=100 * METERS_PER_MILE,
        duration_seconds=7200,
        departure_time=DEPARTURE,
        interval_miles=25,
    )

    midpoint_eta = datetime.fromisoformat(checkpoints[2].eta)

    assert midpoint_eta == DEPARTURE + timedelta(hours=1)


def test_destination_is_included():
    checkpoints = generate_checkpoints(
        geometry=GEOMETRY,
        route_distance_meters=105 * METERS_PER_MILE,
        duration_seconds=7200,
        departure_time=DEPARTURE,
        interval_miles=25,
    )

    assert checkpoints[-1].distance_miles == 105
    assert checkpoints[-1].longitude == -99.0
    assert checkpoints[-1].latitude == 40.0


def test_short_route_has_start_and_destination():
    checkpoints = generate_checkpoints(
        geometry=GEOMETRY,
        route_distance_meters=5 * METERS_PER_MILE,
        duration_seconds=600,
        departure_time=DEPARTURE,
        interval_miles=10,
    )

    assert len(checkpoints) == 2
    assert checkpoints[0].distance_miles == 0
    assert checkpoints[-1].distance_miles == 5


def test_invalid_interval_is_rejected():
    with pytest.raises(ValueError):
        generate_checkpoints(
            GEOMETRY,
            100 * METERS_PER_MILE,
            7200,
            DEPARTURE,
            interval_miles=15,
        )


def test_timezone_is_required():
    with pytest.raises(ValueError):
        generate_checkpoints(
            GEOMETRY,
            100 * METERS_PER_MILE,
            7200,
            datetime(2026, 11, 4, 8, 0),
        )
