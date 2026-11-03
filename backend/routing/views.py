
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from routing.serializers import RoutePlanSerializer
from routing.services.route_scoring import assess_route, rank_routes
from routing.services.weather import WeatherProviderError
from routing.services.checkpoints import (
    METERS_PER_MILE,
    generate_checkpoints,
)
from routing.services.openrouteservice import (
    OpenRouteServiceClient,
    RoutingProviderError,
)


@api_view(["GET"])
def health_check(request):
    return Response({
        "status": "healthy",
        "application": "Spotter Weather Routing",
        "service": "routing-api",
        "version": "1.0.0",
    })


@api_view(["POST"])
def plan_routes(request):
    serializer = RoutePlanSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data

    try:
        client = OpenRouteServiceClient()

        origin = client.geocode(data["origin"])
        destination = client.geocode(data["destination"])

        features = client.get_routes(origin, destination)

        routes = []

        for index, feature in enumerate(features, start=1):
            summary = feature["properties"]["summary"]
            geometry = feature["geometry"]

            distance = summary["distance"]
            duration = summary["duration"]

            checkpoints = generate_checkpoints(
                geometry=geometry["coordinates"],
                route_distance_meters=distance,
                duration_seconds=duration,
                departure_time=data["departure_time"],
                interval_miles=data["checkpoint_interval_miles"],
            )

            routes.append({
                "id": f"route-{index}",
                "distance_miles": round(
                    distance / METERS_PER_MILE, 2
                ),
                "duration_minutes": round(duration / 60, 1),
                "geometry": geometry,
                "checkpoints": [
                    checkpoint.to_dict()
                    for checkpoint in checkpoints
                ],
            })

        recommended_route_id = None
        if data["assess_weather"]:
            for route in routes:
                enriched, summary = assess_route(
                    route["checkpoints"], data["load_weight_lb"]
                )
                route["checkpoints"] = enriched
                route["risk_summary"] = summary.to_dict()
            routes = rank_routes(routes)
            for rank, route in enumerate(routes, start=1):
                route["safety_rank"] = rank
            recommended_route_id = routes[0]["id"] if routes else None

        return Response({
            "origin": {
                "name": origin.name,
                "coordinates": [
                    origin.longitude,
                    origin.latitude,
                ],
            },
            "destination": {
                "name": destination.name,
                "coordinates": [
                    destination.longitude,
                    destination.latitude,
                ],
            },
            "departure_time": data[
                "departure_time"
            ].isoformat(),
            "load_weight_lb": data["load_weight_lb"],
            "routes": routes,
            "route_count": len(routes),
            "requested_route_count": 3,
            "all_requested_routes_available": len(routes) >= 3,
            "weather_assessed": data["assess_weather"],
            "recommended_route_id": recommended_route_id,
        })

    except WeatherProviderError:
        return Response(
            {"error": "Weather forecast unavailable for one or more checkpoints."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    except RoutingProviderError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    except (KeyError, TypeError, ValueError, IndexError):
        return Response(
            {"error": "Routing provider returned invalid route data."},
            status=status.HTTP_502_BAD_GATEWAY,
        )
