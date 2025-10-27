from dateutil.relativedelta import relativedelta
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
from django.views.decorators.csrf import csrf_exempt
from django.db.models.functions import Coalesce
from django.core.cache import cache
from django.db.models import Sum, Avg, Count, Q, Value
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from datetime import datetime, timedelta

from user.models import Driver
from .models import (
    Location,
    Carrier,
    Vehicle,
    Trip,
    TripEvent,
)
from .serializers import (
    LocationSerializer,
    VehicleSerializer,
    TripSerializer,
    TripCreateSerializer,
    TripEventSerializer,
    TripEventCreateSerializer,
)
import re
import math
import logging


logger = logging.getLogger(__name__)


class LocationViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    @action(detail=False, methods=["get"])
    def search(self, request):
        """Search locations by address"""
        query = request.query_params.get("q", "")
        if query:
            locations = self.get_queryset().filter(address__icontains=query)[:10]
            serializer = self.get_serializer(locations, many=True)

            return Response(serializer.data)
        return Response([])


class VehicleViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    permission_classes = [IsAdminUser, IsAuthenticated]
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

    permission_classes = [IsAuthenticated]
    queryset = Trip.objects.select_related(
        "driver", "co_driver", "vehicle__carrier"
    ).prefetch_related("events__location")

    def get_serializer_class(self):
        if self.action == "create":
            return TripCreateSerializer
        return TripSerializer

    @action(detail=True, methods=["post"])
    def add_event(self, request, pk=None):
        """Add a new event to a trip"""
        trip = self.get_object()
        serializer = TripEventCreateSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(trip=trip)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["patch"], url_path="status")
    def update_status(self, request, pk=None):
        """Update the status of a trip (e.g., complete, active)"""
        try:
            trip = self.get_object()
            new_status = request.data.get("status")

            if not new_status:
                return Response(
                    {"error": "Status is required."}, status=status.HTTP_400_BAD_REQUEST
                )

            allowed_statuses = ["active", "complete", "cancelled", "pending"]
            if new_status not in allowed_statuses:
                return Response(
                    {"error": f"Invalid status. Must be one of: {allowed_statuses}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Update the status
            trip.status = new_status
            trip.save(update_fields=["status"])

            return Response(
                {"message": "Status updated successfully", "status": trip.status},
                status=status.HTTP_200_OK,
            )

        except Trip.DoesNotExist:
            return Response(
                {"error": "Trip not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # trip status
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Mark trip as completed"""
        trip = self.get_object()
        trip.is_completed = True
        trip.save()
        return Response({"status": "Trip marked as completed"})

    # Statistics
    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get trip statistics (filtered only by period)"""
        queryset = self.get_queryset()
        now = timezone.now()

        period = request.query_params.get("period")
        if period:
            match = re.match(r"^(\d+)([dwmy])$", period)
            if match:
                value = int(match.group(1))
                unit = match.group(2)

                if unit == "d":
                    delta = timedelta(days=value)
                elif unit == "w":
                    delta = timedelta(weeks=value)
                elif unit == "m":
                    delta = relativedelta(months=value)
                elif unit == "y":
                    delta = relativedelta(years=value)
                else:
                    return Response(
                        {"error": "Invalid period format. Use 1d, 1w, 1m, etc."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                start_date = now - delta
                queryset = queryset.filter(date__gte=start_date, date__lte=now)
            else:
                return Response(
                    {"error": "Invalid period format. Use format like 1d, 3w, 2m, 1y."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            return Response(
                {"error": "Missing 'period' query parameter. Example: ?period=1w"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stats = queryset.aggregate(
            total_trips=Count("id"),
            completed_trips=Count("id", filter=Q(is_completed=True)),
            total_miles=Sum("total_miles_driving"),
            total_driving_hours_sum=Sum("total_driving_hours"),
            avg_miles_per_trip=Avg("total_miles_driving"),
            avg_driving_hours=Avg("total_driving_hours"),
        )

        return Response(stats)

    # Activet trip status
    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get active (incomplete) trips"""
        active_trips = self.get_queryset().filter(is_completed=False)
        serializer = self.get_serializer(active_trips, many=True)
        return Response(serializer.data)


class TripEventViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    permission_classes = [IsAuthenticated]
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


class SearchViewSet(GenericViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        try:
            query = request.GET.get("q", "").strip()
            if not query:
                return Response(
                    {"error": "Search query is required", "status": False},
                    status=400,
                )

            # Pagination setup
            page_size = 10
            page_number = int(request.GET.get("page", 1))
            if page_number < 1:
                page_number = 1

            def paginate_queryset(queryset):
                total = queryset.count()
                total_pages = max(math.ceil(total / page_size), 1)
                if page_number > total_pages:
                    page = 1
                else:
                    page = page_number
                offset = (page - 1) * page_size
                return queryset[offset : offset + page_size], total, page

            # DRIVER SEARCH
            driver_qs = Driver.objects.annotate(
                email_safe=Coalesce("email", Value("")),
            ).filter(
                Q(driver_initial__icontains=query)
                | Q(full_name__icontains=query)
                | Q(license_number__icontains=query)
            )

            if query.isdigit():
                driver_qs = driver_qs.filter(id=int(query))

            drivers_page, driver_total, driver_page_number = paginate_queryset(
                driver_qs
            )
            drivers_data = drivers_page.values("full_name", "email", "license_number")

            # CARRIER SEARCH
            carrier_qs = Carrier.objects.annotate(
                address_safe=Coalesce("address", Value("")),
            ).filter(Q(name__icontains=query) | Q(dot_number__icontains=query))

            if query.isdigit():
                carrier_qs = carrier_qs.filter(id=int(query))

            carriers_page, carrier_total, carrier_page_number = paginate_queryset(
                carrier_qs
            )
            carriers_data = carriers_page.values("dot_number", "name")

            # VEHICLE SEARCH
            truck_qs = Vehicle.objects.annotate(
                truck_number_safe=Coalesce("truck_number", Value("")),
            ).filter(
                Q(license_plate__icontains=query) | Q(truck_number__icontains=query)
            )

            if query.isdigit():
                truck_qs = truck_qs.filter(id=int(query))

            trucks_page, truck_total, truck_page_number = paginate_queryset(truck_qs)
            trucks_data = trucks_page.values(
                "truck_number",
                "make",
                "model",
                "year",
                "vin",
                "license_plate",
                "is_active",
            )

            return Response(
                {
                    "status": True,
                    "query": query,
                    "page": page_number,
                    "drivers": {
                        "count": driver_total,
                        "results": list(drivers_data),
                    },
                    "carriers": {
                        "count": carrier_total,
                        "results": list(carriers_data),
                    },
                    "trucks": {
                        "count": truck_total,
                        "results": list(trucks_data),
                    },
                },
                status=200,
            )

        except Exception as e:
            return Response(
                {
                    "status": False,
                    "message": "Internal server error",
                    "details": str(e),
                },
                status=500,
            )
