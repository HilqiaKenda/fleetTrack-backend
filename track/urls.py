from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    LocationViewSet,
    SearchViewSet,
    VehicleViewSet,
    TripViewSet,
    TripEventViewSet,
)

router = DefaultRouter()
router.register(r"locations", LocationViewSet, basename="location")
router.register(r"vehicles", VehicleViewSet, basename="vehicle")
router.register(r"trips", TripViewSet, basename="trips")
router.register(r"trip-events", TripEventViewSet, basename="event")
router.register(r"", SearchViewSet, basename="search")

urlpatterns = [
    path("", include(router.urls)),
]
