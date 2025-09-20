from rest_framework.mixins import (
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    ListModelMixin,
)
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta

from .models import Location, Driver, Carrier, Vehicle, Trip, TripEvent
from .serializers import (
    LocationSerializer,
    DriverSerializer,
    CarrierSerializer,
    VehicleSerializer,
    TripSerializer,
    TripCreateSerializer,
    TripEventSerializer,
    TripEventCreateSerializer,
)
import traceback


class LocationViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer

    @action(detail=False, methods=["get"])
    def search(self, request):
        """Search locations by address"""
        query = request.query_params.get("q", "")
        if query:
            locations = self.get_queryset().filter(address__icontains=query)[:10]
            serializer = self.get_serializer(locations, many=True)

            return Response(serializer.data)
        return Response([])


class DriverViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer

    @action(detail=True, methods=["get"])
    def trips(self, request, pk=None):
        """Get trips for a specific driver"""
        driver = self.get_object()
        trips = Trip.objects.filter(driver=driver).order_by("-date")
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def hours_summary(self, request, pk=None):
        """Get hours summary for a driver"""
        driver = self.get_object()
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        trips = Trip.objects.filter(driver=driver)
        if date_from:
            trips = trips.filter(date__gte=date_from)
        if date_to:
            trips = trips.filter(date__lte=date_to)

        summary = trips.aggregate(
            total_driving_hours=Sum("total_driving_hours"),
            total_on_duty_hours=Sum("total_on_duty_hours"),
            total_miles=Sum("total_miles_driving"),
            trip_count=Count("id"),
        )

        return Response(summary)


class CarrierViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    queryset = Carrier.objects.all()
    serializer_class = CarrierSerializer


class VehicleViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    queryset = Vehicle.objects.select_related("carrier")
    serializer_class = VehicleSerializer

    @action(detail=True, methods=["get"])
    def trips(self, request, pk=None):
        """Get trips for a specific vehicle"""
        vehicle = self.get_object()
        trips = Trip.objects.filter(vehicle=vehicle).order_by("-date")
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)


class TripViewSet(
    CreateModelMixin,
    UpdateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):

    queryset = Trip.objects.select_related(
        "driver", "co_driver", "vehicle__carrier"
    ).prefetch_related("events__location")
    # print(traceback.format_exc())

    def get_serializer_class(self):
        if self.action == "create":
            return TripCreateSerializer
        # print(traceback.format_exc())
        return TripSerializer

    @action(detail=True, methods=["post"])
    def add_event(self, request, pk=None):
        """Add a new event to a trip"""
        trip = self.get_object()
        serializer = TripEventCreateSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(trip=trip)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        # print(traceback.format_exc())
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Mark trip as completed"""
        trip = self.get_object()
        trip.is_completed = True
        trip.save()
        # print(traceback.format_exc())
        return Response({"status": "Trip marked as completed"})

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get trip statistics"""
        queryset = self.get_queryset()

        # Filter by date range if provided
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        stats = queryset.aggregate(
            total_trips=Count("id"),
            completed_trips=Count("id", filter=Q(is_completed=True)),
            total_miles=Sum("total_miles_driving"),
            total_driving_hours_sum=Sum("total_driving_hours"),
            avg_miles_per_trip=Avg("total_miles_driving"),
            avg_driving_hours=Avg("total_driving_hours"),
        )
        # print(traceback.format_exc())

        return Response(stats)

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get active (incomplete) trips"""
        active_trips = self.get_queryset().filter(is_completed=False)
        serializer = self.get_serializer(active_trips, many=True)
        # print(traceback.format_exc())
        return Response(serializer.data)

    # print(traceback.format_exc())


class TripEventViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    queryset = TripEvent.objects.select_related("trip", "location")

    def get_serializer_class(self):
        if self.action == "create":
            return TripEventCreateSerializer
        return TripEventSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        trip_id = self.request.query_params.get("trip")
        if trip_id:
            queryset = queryset.filter(trip__id=trip_id)
        return queryset

    @action(detail=False, methods=["get"])
    def recent(self, request):
        """Get recent events"""
        hours = int(request.query_params.get("hours", 24))
        since = timezone.now() - timedelta(hours=hours)

        recent_events = (
            self.get_queryset().filter(timestamp__gte=since).order_by("-timestamp")[:50]
        )

        serializer = self.get_serializer(recent_events, many=True)
        return Response(serializer.data)
