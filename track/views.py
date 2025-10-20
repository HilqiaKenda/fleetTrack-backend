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
from django.core.cache import cache
from django.db.models import Sum, Avg, Count, Q
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
                            "code": "INVALID_REQUEST",
                            "message": "Invalid date range specified",
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check cache
            cache_key = f"admin_dashboard_{period}_{branch_ids}_{include_inactive}"
            cached_data = cache.get(cache_key)
            if cached_data:
                return Response(
                    {
                        "status": "success",
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
                    "status": "error",
                    "error": {"code": "INVALID_REQUEST", "message": str(e)},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            logger.error(f"Dashboard generation error: {str(e)}", exc_info=True)
            print(traceback.format_exc)
            return Response(
                {
                    "status": "error",
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Failed to generate dashboard data",
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

    # def _calculate_date_range(self, date_range):
    #     """Calculate start and end dates based on range"""
    #     now = timezone.now()

    #     ranges = {
    #         "today": timedelta(days=0),
    #         "yesterday": timedelta(days=1),
    #         "last_7_days": timedelta(days=7),
    #         "last_30_days": timedelta(days=30),
    #         "last_90_days": timedelta(days=90),
    #     }

    #     if date_range in ranges:
    #         return {"start": now - ranges[date_range], "end": now}
    #     return None

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
