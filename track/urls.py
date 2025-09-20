from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LocationViewSet,
    DriverViewSet,
    CarrierViewSet,
    VehicleViewSet,
    TripViewSet,
    TripEventViewSet,
)

router = DefaultRouter()
router.register(r"locations", LocationViewSet)
router.register(r"drivers", DriverViewSet)
router.register(r"carriers", CarrierViewSet)
router.register(r"vehicles", VehicleViewSet)
router.register(r"trips", TripViewSet)
router.register(r"trip-events", TripEventViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
