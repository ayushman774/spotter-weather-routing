
from django.urls import path

from routing.views import health_check, plan_routes

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("routes/plan/", plan_routes, name="plan-routes"),
]
