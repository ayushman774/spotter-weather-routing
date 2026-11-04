
from django.urls import path

from routing.views import health_check, plan_routes, corridor_forecast

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("routes/plan/", plan_routes, name="plan-routes"),
    path("weather/corridor/", corridor_forecast, name="corridor-forecast"),
]
