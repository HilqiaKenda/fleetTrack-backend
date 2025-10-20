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
from django.db.models.functions import Coalesce
from django.core.cache import cache
from django.db.models import Sum, Avg, Count, Q, Value
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from datetime import datetime, timedelta
from .models import (
    AlertLog,
    Location,
    Driver,
    Carrier,
    UserActivityLog,
    Vehicle,
    Trip,
    TripEvent,
)
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
import re
import math
import logging
import traceback


logger = logging.getLogger(__name__)


class AdminDashboardViewSet(GenericViewSet):
    # permission_classes = [IsAuthenticated, IsAdminUser]

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get comprehensive admin dashboard data"""
        try:
            # Parse request parameters
            period = request.query_params.get("period", "last_30_days")
            branch_ids = request.query_params.get("branch_ids")
            include_inactive = (
                request.query_params.get("include_inactive", "false").lower() == "true"
            )

            # Calculate date range
            period_filter = self._calculate_period_range(period)
            if not period_filter:
                return Response(
                    {
                        "status": "error",
                        "error": {
                            "status": False,
                            "message": "Invalid period range specified",
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check cache
            cache_key = f"admin_dashboard_{period}_{branch_ids}_{include_inactive}"
            print(cache_key)
            cached_data = cache.get(cache_key)
            if cached_data:
                return Response(
                    {
                        "status": True,
                        "meassge": "success",
                        "data": cached_data,
                        "metadata": {
                            "from_cache": True,
                            "generated_at": timezone.now().isoformat(),
                        },
                    }
                )

            # Build queryset filters
            vehicle_filter = Q()
            trip_filter = Q(
                date__gte=period_filter["start"], date__lte=period_filter["end"]
            )

            if branch_ids:
                branch_list = [int(b) for b in branch_ids.split(",")]
                vehicle_filter &= Q(carrier__branch_id__in=branch_list)
                trip_filter &= Q(vehicle__carrier__branch_id__in=branch_list)

            if not include_inactive:
                vehicle_filter &= Q(is_active=True)

            overview_data = self._get_overview_data(vehicle_filter, trip_filter)
            vehicle_distribution = self._get_vehicle_distribution(vehicle_filter)
            operations_metrics = self._get_operations_metrics(trip_filter)
            alerts_summary = self._get_alerts_summary(period_filter)
            user_activity = self._get_user_activity(period_filter)
            financial_overview = self._get_financial_overview(trip_filter)
            system_health = self._get_system_health()
            dashboard_data = {
                "overview": overview_data,
                "vehicle_distribution": vehicle_distribution,
                "operations_metrics": operations_metrics,
                "alerts_summary": alerts_summary,
                "user_activity": user_activity,
                "financial_overview": financial_overview,
                "system_health": system_health,
            }

            # Cache for 5 minutes
            cache.set(cache_key, dashboard_data, 300)

            # Log activity
            UserActivityLog.objects.create(
                # user=request.user,
                action="view_admin_dashboard",
                resource_type="dashboard",
                ip_address=self._get_client_ip(request),
                device_info=request.META.get("HTTP_USER_AGENT", ""),
            )

            return Response(
                {
                    "status": "success",
                    "data": dashboard_data,
                    "metadata": {
                        "generated_at": timezone.now().isoformat(),
                        "date_range": {
                            "start": period_filter["start"].isoformat(),
                            "end": period_filter["end"].isoformat(),
                        },
                    },
                }
            )

        except ValueError as e:
            logger.error(f"Invalid parameter: {str(e)}")
            return Response(
                {
                    "status": False,
                    "error": {"message": "error", "details": str(e)},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            logger.error(f"Dashboard generation error: {str(e)}", exc_info=True)
            print(traceback.format_exc)
            return Response(
                {
                    "status": False,
                    "error": {
                        "message": "error",
                        "details": "Failed to generate dashboard data",
                        "request_id": f"req_{int(timezone.now().timestamp())}",
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _calculate_period_range(self, date_range):
        """Calculate start and end dates based on range or period string"""
        now = timezone.now()

        # Predefined ranges
        predefined = {
            "today": now.replace(hour=0, minute=0, second=0, microsecond=0),
            "yesterday": now - timedelta(days=1),
            "last_7_days": now - timedelta(days=7),
            "last_30_days": now - timedelta(days=30),
            "last_90_days": now - timedelta(days=90),
            "last_180_days": now - timedelta(days=180),
        }

        if date_range in predefined:
            start = predefined[date_range]
            return {"start": start, "end": now}

        # Match dynamic periods like 1d, 3d, 1w, 1m, etc.
        match = re.match(r"^(\d+)([dwmy])$", date_range)
        if match:
            value, unit = int(match.group(1)), match.group(2)
            if unit == "d":
                delta = timedelta(days=value)
            elif unit == "w":
                delta = timedelta(weeks=value)
            elif unit == "m":
                delta = relativedelta(months=value)
            elif unit == "y":
                delta = relativedelta(years=value)
            else:
                return None

            start = now - delta
            return {"start": start, "end": now}

        return None

    def _get_overview_data(self, vehicle_filter, trip_filter):
        """Aggregate overview statistics"""
        vehicles = Vehicle.objects.filter(vehicle_filter)
        trips = Trip.objects.filter(trip_filter)

        return {
            "total_vehicles": vehicles.count(),
            "active_vehicles": vehicles.filter(is_active=True).count(),
            "inactive_vehicles": vehicles.filter(is_active=False).count(),
            "total_drivers": Driver.objects.count(),
            "total_branches": Carrier.objects.count(),
            "total_trips_period": trips.count(),
            "completed_trips": trips.filter(is_completed=True).count(),
            "in_progress_trips": trips.filter(is_completed=False).count(),
        }

    def _get_vehicle_distribution(self, vehicle_filter):
        """Return vehicle count grouped by carrier"""
        vehicles = Vehicle.objects.filter(vehicle_filter)
        return list(
            vehicles.values("carrier__name")
            .annotate(vehicle_count=Count("id"))
            .order_by("-vehicle_count")
        )

    def _get_operations_metrics(self, trip_filter):
        """Return total miles, avg miles, total hours driven"""
        trips = Trip.objects.filter(trip_filter)

        total_miles = trips.aggregate(total=Count("total_miles_driving"))["total"] or 0
        avg_miles = trips.aggregate(avg=Count("total_mileage_today"))["avg"] or 0
        total_driving_hours = (
            trips.aggregate(total=Count("total_driving_hours"))["total"] or 0
        )

        return {
            "total_miles_driving": total_miles,
            "average_miles_per_day": avg_miles,
            "total_driving_hours": total_driving_hours,
        }

    def _get_alerts_summary(self, date_filter):
        """Group alerts by severity and resolution status"""
        alerts = AlertLog.objects.filter(
            created_at__range=(date_filter["start"], date_filter["end"])
        )

        severity_counts = alerts.values("severity").annotate(count=Count("id"))
        unresolved_count = alerts.filter(is_resolved=False).count()
        resolved_count = alerts.filter(is_resolved=True).count()

        return {
            "severity_breakdown": severity_counts,
            "resolved_alerts": resolved_count,
            "unresolved_alerts": unresolved_count,
            "total_alerts": alerts.count(),
        }

    def _get_user_activity(self, date_filter):
        """Activity log summary (based on action/resource_type)"""
        logs = UserActivityLog.objects.filter(
            timestamp__range=(date_filter["start"], date_filter["end"])
        )

        return {
            "total_actions": logs.count(),
            "actions_by_type": list(
                logs.values("action").annotate(count=Count("id")).order_by("-count")
            ),
            "resources_accessed": list(
                logs.values("resource_type").annotate(count=Count("id"))
            ),
        }

    def _get_financial_overview(self, trip_filter):
        """Stub for future financial data"""

        # No financial models provided – return placeholders
        return {
            "total_revenue": None,
            "total_costs": None,
            "profit_margin": None,
        }

    def _get_system_health(self):
        """System diagnostics placeholder"""
        return {
            "cache_status": "healthy" if cache else "unavailable",
            "uptime": "N/A",
            "database_status": "connected",  # Not actually validated here
        }

    def _get_client_ip(self, request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


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

    @action(detail=True, methods=["patch"], url_path="update-status")
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
    # permission_classes = [IsAuthenticated, IsAdminUser]

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
