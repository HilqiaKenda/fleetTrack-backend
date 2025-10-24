from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AdminDashboardViewSet,
    DriverDashboardViewSet,
    LocationViewSet,
    DriverViewSet,
    CarrierViewSet,
    SearchViewSet,
    VehicleViewSet,
    TripViewSet,
    TripEventViewSet,
)

router = DefaultRouter()
router.register(r"locations", LocationViewSet, basename="location")
router.register(r"admin", AdminDashboardViewSet, basename="admin-dash")
router.register(r"driver-dashboard", DriverDashboardViewSet, basename="driver-dash")
router.register(r"drivers", DriverViewSet, basename="driver")
router.register(r"carriers", CarrierViewSet, basename="carrier")
router.register(r"vehicles", VehicleViewSet, basename="vehicle")
router.register(r"trips", TripViewSet, basename="trips")
router.register(r"trip-events", TripEventViewSet, basename="event")
router.register(r"", SearchViewSet, basename="search")

urlpatterns = [
    path("", include(router.urls)),
]
