import logging
import re
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken
from track.models import AlertLog, Trip, UserActivityLog, Vehicle
from track.serializers import TripSerializer

from user.serializers import CarrierSerializer, DriverSerializer
from user.utilities.auth import CookieJWTAuthentication

# from utilities.permissions import
# from utilities.permissions import
from user.utilities.permissions import (
    MANAGER_ROLES,
    ROLE_ADMIN,
    ROLE_BRANCH_MANAGER,
    ROLE_DRIVER,
    ROLE_FLEET_MANAGER,
    ROLE_ORGANIZATION,
    DriverMixin,
    RolePermission,
    ScopedQuerysetMixin,
)

from .models import Branch, BranchAssignment, BranchManager, Carrier, Driver, Organization, User
from .serializers import (
    BranchAssignmentSerializer,
    BranchDetailSerializer,
    BranchListSerializer,
    BranchManagerSerializer,
    BranchSerializer,
    BranchStatisticsSerializer,
    CreateBranchManagerSerializer,
    OrganizationRegisterSerializer,
    OrganizationSerializer,
    LoginSerializer,
    RefreshSerializer,
    RegisterSerializer,
    UpdateUserProfileSerializer,
    UserProfileSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


class RegisterViewSet(GenericViewSet):
    """
    Register a new user and return JWT tokens in response
    """

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": UserSerializer(user).data,
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "message": "User registered successfully",
            },
            status=status.HTTP_201_CREATED,
        )


class LoginViewSet(GenericViewSet):
    """
    Authenticate user and return JWT tokens in response
    """

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": UserSerializer(user).data,
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "message": "Login successful",
            },
            status=status.HTTP_200_OK,
        )


class LogoutViewSet(GenericViewSet):
    """
    Logout user by blacklisting refresh token
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh_token")

        if not refresh_token:
            return Response(
                {"detail": "Refresh token required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Successfully logged out."},
            status=status.HTTP_200_OK,
        )


class RefreshTokenViewSet(GenericViewSet):
    """
    Refresh access token using refresh token
    """

    permission_classes = [AllowAny]
    serializer_class = RefreshSerializer

    def create(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh_token")

        if not refresh_token:            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)

            # Check if blacklisted
            jti = token.get("jti")
            if BlacklistedToken.objects.filter(token__jti=jti).exists():
                return Response(
                    {"detail": "Token has been blacklisted. Please login again."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            new_access = str(token.access_token)
            return Response(
                {
                    "access_token": new_access,
                    "refresh_token": str(token),
                    "message": "Token refreshed successfully",
                },
                status=status.HTTP_200_OK,
            )

        except TokenError:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class MeViewSet(RetrieveModelMixin, UpdateModelMixin, GenericViewSet):
    """
    Current User Profile ViewSet
    """

    permission_classes = [IsAuthenticated]
    # authentication_classes = [CookieJWTAuthentication]

    def get_object(self):
        """Return the current authenticated user"""
        return self.request.user

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.request.method in ["PUT", "PATCH"]:
            return UpdateUserProfileSerializer
        return UserProfileSerializer

    def retrieve(self, request, *args, **kwargs):
        """Get current user profile"""
        serializer = self.get_serializer(self.get_object())
        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        """Full update current user profile"""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "user": UserProfileSerializer(instance).data,
                "message": "Profile updated successfully",
            },
            status=status.HTTP_200_OK,
        )

    def partial_update(self, request, *args, **kwargs):
        """Partial update current user profile"""
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


class SessionAuthViewSet(GenericViewSet):
    """
    Check Authentication Status ViewSet
    """

    permission_classes = [IsAuthenticated]
    # authentication_classes = [CookieJWTAuthentication]
    serializer_class = UserSerializer

    def list(self, request, *args, **kwargs):
        """Check if user is authenticated (useful for frontend)"""
        return Response(
            {
                "authenticated": True,
                "user": UserSerializer(request.user).data,
            },
            status=status.HTTP_200_OK,
        )


class UserManagementViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    """
    User Management ViewSet - For admin user management
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    # authentication_classes = [CookieJWTAuthentication]

    def get_queryset(self):
        """Filter users based on role permissions"""
        user = self.request.user

        # Admin sees all users
        if user.role == "admin":
            return User.objects.all()

        # Fleet managers see users in their branches
        if user.role in ["fleet-manager", "branch-manager"]:
            # Add your branch filtering logic here
            return User.objects.filter(is_active=True)

        # Others see only themselves
        return User.objects.filter(id=user.id)

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return RegisterSerializer
        elif self.action in ["update", "partial_update"]:
            return UpdateUserProfileSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        """Only admin can create users"""
        if request.user.role != "admin":
            return Response(
                {"error": "Only administrators can create users."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Only admin can delete users"""
        if request.user.role != "admin":
            return Response(
                {"error": "Only administrators can delete users."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        """List all users with pagination"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        return Response({"count": queryset.count(), "users": serializer.data})


class AdminDashboardViewSet(GenericViewSet):
    permission_classes = [
        IsAuthenticated,
        IsAdminUser,
        RolePermission.for_roles([ROLE_ADMIN]),
    ]
    pagination_class = None

    def get_serializer_class(self):
        return OrganizationSerializer

    @action(detail=False, methods=["get", "post", "put"])
    def summary(self, request):
        """Get comprehensive admin dashboard data"""
        try:
            # request parameters
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
            trip_summary = self._get_trip_summary(trip_filter)
            vehicle_distribution = self._get_vehicle_distribution(vehicle_filter)
            operations_metrics = self._get_operations_metrics(trip_filter)
            alerts_summary = self._get_alerts_summary(period_filter)
            user_activity = self._get_user_activity(period_filter)
            financial_overview = self._get_financial_overview(trip_filter)
            system_health = self._get_system_health()
            dashboard_data = {
                "overview": overview_data,
                "trips_summary": trip_summary,
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
                    "message": "error",
                    "details": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            logger.error(f"Dashboard generation error: {str(e)}", exc_info=True)
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
        vehicles = Vehicle.objects.values_list("id", "is_active").filter(vehicle_filter)
        trips = Trip.objects.values_list("id").filter(trip_filter)

        return {
            "total_vehicles": vehicles.count(),
            "trips_summary": Trip.objects.values_list("id").count(),
            "active_vehicles": vehicles.filter(is_active=True).count(),
            "inactive_vehicles": vehicles.filter(is_active=False).count(),
            "total_drivers": Driver.objects.values_list("id").count(),
            "total_branches": Carrier.objects.values_list("id").count(),
            "total_trips_period": trips.count(),
            "completed_trips": trips.filter(is_completed=True).count(),
            "in_progress_trips": trips.filter(is_completed=False).count(),
        }

    def _get_trip_summary(self, trip_filter):
        """Return count of trips by status + total trips"""
        trips = Trip.objects.filter(trip_filter)

        # Group by status
        status_counts = trips.values("status").annotate(count=Count("id")).order_by()

        # Convert list → dictionary for easy frontend use
        status_dict = {item["status"]: item["count"] for item in status_counts}

        return {
            "total_trips": trips.count(),
            "status_breakdown": {
                "active": status_dict.get("active", 0),
                "assigned": status_dict.get("assigned", 0),
                "schedule": status_dict.get("schedule", 0),
                "completed": status_dict.get("completed", 0),
                "cancelled": status_dict.get("cancelled", 0),
            },
        }

    def _get_vehicle_distribution(self, vehicle_filter):
        """Return vehicle count grouped by carrier"""
        vehicles = (
            Vehicle.objects.prefetch_related("carrier", "branch")
            .select_related("carrier", "branch")
            .filter(vehicle_filter)
        )
        return list(
            vehicles.values("carrier__name")
            .annotate(vehicle_count=Count("id"))
            .order_by("-vehicle_count")
        )

    def _get_operations_metrics(self, trip_filter):
        """Return total miles, avg miles, total hours driven"""
        trips = (
            Trip.objects.prefetch_related("driver", "co_driver", "vehicle")
            .select_related("driver", "co_driver", "vehicle")
            .filter(trip_filter)
        )

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



class OrganizationRegisterViewSet(GenericViewSet):
    """
    Register organization + login credentials
    """

    serializer_class = OrganizationRegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        organization = serializer.save()
        user = organization.owner

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "organization": OrganizationSerializer(organization).data,
                "user": UserSerializer(user).data,
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "message": "Organization registered successfully",
            },
            status=status.HTTP_201_CREATED,
        )


class OrganizationViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    """
    Organization Management ViewSet
    """

    permission_classes = [
        IsAuthenticated,
        IsAdminUser,
        RolePermission.for_roles([ROLE_ORGANIZATION]),
    ]

    queryset = Organization.objects.all().prefetch_related(
        "branches",
        "users",
    )

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "code", "status", "industry"]
    ordering_fields = ["name", "status", "created_at"]

    serializer_class = OrganizationSerializer

    @action(detail=True, methods=["get"])
    def statistics(self, request, pk=None):
        """Return aggregated statistics for an organization"""

        organization = self.get_object()

        # Branch data
        total_branches = organization.get_branch_count()
        active_branches = organization.get_active_branches().count()

        # User data
        total_users = organization.get_user_count()

        # Vehicles (safe defaults if model not implemented yet)
        total_vehicles = getattr(organization, "vehicles", []).count() if hasattr(organization, "vehicles") else 0
        active_vehicles = getattr(
            organization.vehicles.filter(status="active"),
            "count",
            lambda: 0,
        )() if hasattr(organization, "vehicles") else 0

        inactive_vehicles = total_vehicles - active_vehicles

        # Trips (safe placeholders)
        active_trips = 0
        completed_trips = 0

        # Maintenance
        maintenance_pending = 0

        data = {
            "organization_id": organization.id,
            "organization_name": organization.name,
            "total_branches": total_branches,
            "active_branches": active_branches,
            "total_users": total_users,
            "total_vehicles": total_vehicles,
            "active_vehicles": active_vehicles,
            "inactive_vehicles": inactive_vehicles,
            "active_trips": active_trips,
            "completed_trips": completed_trips,
            "maintenance_pending": maintenance_pending,
        }

        serializer = OrganizationStatisticsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DriverDashboardViewSet(GenericViewSet):
    permission_classes = [
        IsAuthenticated,
        RolePermission.for_roles([ROLE_ADMIN, ROLE_DRIVER]),
    ]
    pagination_class = None

    @action(detail=False, methods=["get"], url_path="summary")
    def driver_summary(self, request):
        # driver_id = request.query_params.get("driver_id")
        driver_id = 5
        if not driver_id:
            return Response(
                {"status": False, "message": "Driver ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            driver = (
                Driver.objects.prefetch_related("user", "branch")
                .select_related("user", "branch")
                .get(id=driver_id)
            )
        except Driver.DoesNotExist:
            return Response(
                {"status": False, "message": "Driver not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get all trips by this driver
        all_trips = (
            Trip.objects.prefetch_related("driver", "co_driver", "vehicle")
            .select_related("driver", "co_driver", "vehicle")
            .filter(driver_id=driver.id)
        )
        trips_count = (
            Trip.objects.prefetch_related("driver", "co_driver", "vehicle")
            .select_related("driver", "co_driver", "vehicle")
            .filter(driver_id=driver.id)
            .count()
        )

        # Get all vehicles used
        vehicle_ids = all_trips.values_list("vehicle_id", flat=True).distinct()
        used_vehicles = (
            Vehicle.objects.prefetch_related("carrier", "branch")
            .select_related("carrier", "branch")
            .filter(id__in=vehicle_ids)
        )
        all_vehicles = (
            Vehicle.objects.prefetch_related("branch", "carrier")
            .select_related("carrier", "branch")
            .filter(id__in=vehicle_ids)
            .count()
        )

        # Get current assigned trip
        current_trip = all_trips.filter(
            Q(status="ongoing") | Q(status="assigned")
        ).first()

        # Get current assigned vehicle
        current_vehicle = current_trip.vehicle if current_trip else None

        # Driver details (basic record)
        driver_record = {
            "id": driver.id,
            "name": driver.user.username,
            "email": driver.email,
            "phone": driver.phone_number,
        }

        # Serialize trip and vehicle data as needed or use DRF serializers if available
        trip_data = list(all_trips.values())
        vehicle_data = list(used_vehicles.values())
        current_trip_data = current_trip.id if current_trip else None
        current_vehicle_data = current_vehicle.id if current_vehicle else None

        return Response(
            {
                "status": True,
                "data": {
                    "driver": driver_record,
                    "current_vehicle_id": current_vehicle_data,
                    "current_trip_id": current_trip_data,
                    "used_vehicles": all_vehicles,
                    "trips_count": trips_count,
                    "all_trips": trip_data,
                    # "used_vehicles": vehicle_data,
                },
            },
            status=status.HTTP_200_OK,
        )


class DriverViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    queryset = (
        Driver.objects.prefetch_related("user", "branch")
        .select_related("user", "branch")
        .all()
    )
    serializer_class = DriverSerializer
    # permission_classes = [IsAuthenticated, RolePermission([ROLE_DRIVER, ROLE_ADMIN])]

    @action(detail=True, methods=["get"])
    def trips(self, request, pk=None):
        """Get trips for a specific driver"""
        driver = self.get_object()
        trips = (
            Trip.objects.prefetch_related("driver", "co_driver")
            .select_related("driver", "co_driver")
            .filter(driver=driver)
            .order_by("-date")
        )
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def hours_summary(self, request, pk=None):
        """Get hours summary for a driver"""
        driver = self.get_object()
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        trips = (
            Trip.objects.prefetch_related("driver", "co_driver")
            .select_related("driver", "co_driver")
            .filter(driver=driver)
        )
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
    # permission_classes = [IsAuthenticated, IsAuthenticated]


class BranchViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    """
    Branch management
    """

    queryset = (
        Branch.objects.all()
        .prefetch_related("branch_managers")
        .select_related("branch_managers")
    )
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "code", "city", "region", "status"]
    ordering_fields = ["name", "city", "region", "status", "created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return BranchListSerializer
        elif self.action == "retrieve":
            return BranchDetailSerializer
        return BranchSerializer

    @action(detail=True, methods=["get"])
    def managers(self, request, pk=None):
        """Return all active managers for this branch."""
        branch = self.get_object()
        managers = branch.branch_managers.filter(is_active=True)
        serializer = BranchManagerSerializer(managers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def statistics(self, request, pk=None):
        """Return detailed statistics for a single branch."""
        branch = self.get_object()
        data = {
            "branch_id": branch.id,
            "branch_name": branch.name,
            "total_vehicles": branch.get_vehicle_count(),
            "active_vehicles": branch.get_active_vehicle_count(),
            "inactive_vehicles": branch.get_vehicle_count(),
            "total_drivers": branch.get_driver_count(),
            "active_trips": 0,
            "completed_trips": 0,
            "maintenance_pending": 0,
            "capacity_usage": (
                f"{(branch.get_vehicle_count() / branch.capacity * 100):.1f}%"
                if branch.capacity > 0
                else "N/A"
            ),
        }
        serializer = BranchStatisticsSerializer(data)
        return Response(serializer.data)


class BranchManagerViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    """
    Branch Manager management.
    """

    queryset = BranchManager.objects.prefetch_related("branch", "user").select_related(
        "branch", "user"
    )
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["user__username", "branch__name", "role"]
    ordering_fields = ["assigned_date", "is_primary", "is_active"]

    def get_serializer_class(self):
        if self.action == "create":
            return CreateBranchManagerSerializer
        return BranchManagerSerializer

    @action(detail=False, methods=["get"], url_path="by-branch/(?P<branch_id>[^/.]+)")
    def by_branch(self, request, branch_id=None):
        """List all active managers for a specific branch."""
        managers = self.queryset.filter(branch_id=branch_id, is_active=True)
        serializer = self.get_serializer(managers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="by-user/(?P<user_id>[^/.]+)")
    def by_user(self, request, user_id=None):
        """List all branches managed by a given user."""
        managers = self.queryset.filter(user_id=user_id, is_active=True)
        serializer = self.get_serializer(managers, many=True)
        return Response(serializer.data)


class BranchAssignmentViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    """
    Branch Assignments (staff/driver assignments).
    """

    queryset = BranchAssignment.objects.prefetch_related(
        "branch", "user"
    ).select_related("branch", "user")
    serializer_class = BranchAssignmentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["user__username", "branch__name", "assignment_type"]
    ordering_fields = ["start_date", "end_date", "is_active"]

    @action(detail=False, methods=["get"], url_path="by-branch/(?P<branch_id>[^/.]+)")
    def by_branch(self, request, branch_id=None):
        """List all active assignments in a branch."""
        assignments = self.queryset.filter(branch_id=branch_id, is_active=True)
        serializer = self.get_serializer(assignments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="by-user/(?P<user_id>[^/.]+)")
    def by_user(self, request, user_id=None):
        """List all branch assignments for a user."""
        assignments = self.queryset.filter(user_id=user_id, is_active=True)
        serializer = self.get_serializer(assignments, many=True)
        return Response(serializer.data)


class BranchStatisticsViewSet(GenericViewSet, ListModelMixin):
    """
    statistics across all branches.
    """

    serializer_class = BranchStatisticsSerializer

    def list(self, request, *args, **kwargs):
        """Return aggregated statistics for all branches."""
        branches = (
            Branch.objects.select_related("organization")
            .select_related("organization")
            .all()
        )
        data = []

        for branch in branches:
            data.append(
                {
                    "branch_id": branch.id,
                    "branch_name": branch.name,
                    "total_vehicles": branch.get_vehicle_count(),
                    "active_vehicles": branch.get_active_vehicle_count(),
                    "inactive_vehicles": branch.get_vehicle_count()
                    - branch.get_active_vehicle_count(),
                    "total_drivers": branch.get_driver_count(),
                    "active_trips": 0,
                    "completed_trips": 0,
                    "maintenance_pending": 0,
                    "capacity_usage": (
                        f"{(branch.get_vehicle_count() / branch.capacity * 100):.1f}%"
                        if branch.capacity > 0
                        else "N/A"
                    ),
                }
            )

        serializer = self.get_serializer(data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    