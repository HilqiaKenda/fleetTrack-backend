# permissions.py
<<<<<<< Updated upstream
from functools import wraps

from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from user.models import Branch

# 🔹 Central Role Definitions
=======

from functools import wraps
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from user.models import Branch


# === ROLE CONSTANTS ===
>>>>>>> Stashed changes
ROLE_ADMIN = "admin"
ROLE_ORGANIZATION = "organization"
ROLE_FLEET_MANAGER = "fleet-manager"
ROLE_MAINTENANCE = "maintenancer"
ROLE_DRIVER = "driver"
ROLE_BRANCH_MANAGER = "branch-manager"

# === ROLE GROUPS ===
ADMIN_ROLES = [ROLE_ADMIN]
ORGANIZATION_ROLES = [
    ROLE_ORGANIZATION,
    ROLE_FLEET_MANAGER,
    ROLE_MAINTENANCE,
    ROLE_DRIVER,
    ROLE_BRANCH_MANAGER,
]
MANAGER_ROLES = [ROLE_ADMIN, ROLE_ORGANIZATION, ROLE_FLEET_MANAGER]
MAINTENANCE_ROLES = [ROLE_ADMIN, ROLE_ORGANIZATION, ROLE_MAINTENANCE]
ALL_ROLES = [
    ROLE_ADMIN,
    ROLE_ORGANIZATION,
    ROLE_FLEET_MANAGER,
    ROLE_MAINTENANCE,
    ROLE_DRIVER,
    ROLE_BRANCH_MANAGER,
]


<<<<<<< Updated upstream
# 🔹 Generic DRF Permission
=======
>>>>>>> Stashed changes
class RolePermission(BasePermission):
    """
    DRF permission that checks if user has one of the allowed roles.
    Usage:
        permission_classes = [RolePermission.for_roles(['admin', 'fleet-manager'])]
    """

    allowed_roles = []

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and (not self.allowed_roles or request.user.role in self.allowed_roles)
        )

    @classmethod
    def for_roles(cls, roles):
        """Factory method for specific role permissions."""

        class _RolePermission(cls):
            allowed_roles = roles

        _RolePermission.__name__ = f"RolePermission_{'_'.join(roles)}"
        return _RolePermission


<<<<<<< Updated upstream
# 🔹 Unified Role-Based Mixin
=======
>>>>>>> Stashed changes
class RolePermissionMixin:
    """Reusable mixin to enforce role-based access control on views."""

    required_roles = []

    def check_role_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            raise PermissionDenied("Authentication required.")
        if self.required_roles and user.role not in self.required_roles:
            raise PermissionDenied(
                f"This action requires one of the following roles: {', '.join(self.required_roles)}"
            )

    def dispatch(self, request, *args, **kwargs):
        self.check_role_permission()
        return super().dispatch(request, *args, **kwargs)


<<<<<<< Updated upstream
# 🔹 Unified Data Filtering Mixin
=======
>>>>>>> Stashed changes
class ScopedQuerysetMixin:
    """
    Automatically filter queryset by user's scope:
    - Admin: all data
    - Organization: all its branches' data
    - Fleet Manager / Maintenancer: own branch
    - Driver: own records
    """

    branch_field = "branch"
    driver_field = "driver"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if not user.is_authenticated:
            return qs.none()

        # Admins see all
        if user.role == ROLE_ADMIN:
            return qs

        # Organization-level: can see all branches under their organization
        if user.role == ROLE_ORGANIZATION and hasattr(user, "organization"):
            return qs.filter(**{"branch__organization": user.organization})

        # Branch-based roles
        if user.role in [ROLE_FLEET_MANAGER, ROLE_MAINTENANCE, ROLE_BRANCH_MANAGER]:
            if hasattr(user, "branch") and user.branch:
                return qs.filter(**{self.branch_field: user.branch})
            return qs.none()

        # Driver-specific filtering
        if user.role == ROLE_DRIVER:
            if hasattr(qs.model, self.driver_field):
                return qs.filter(**{self.driver_field: user})
            if hasattr(qs.model, "assigned_driver"):
                return qs.filter(assigned_driver=user)

        return qs.none()


<<<<<<< Updated upstream
# 🔹 Specialized Mixins
=======
>>>>>>> Stashed changes
class AdminOnlyMixin(RolePermissionMixin):
    required_roles = ADMIN_ROLES


class OrganizationOnlyMixin(RolePermissionMixin):
    required_roles = ORGANIZATION_ROLES


class FleetManagerMixin(RolePermissionMixin):
    required_roles = MANAGER_ROLES


class MaintenanceSupervisorMixin(RolePermissionMixin):
    required_roles = MAINTENANCE_ROLES


class DriverMixin(RolePermissionMixin):
    required_roles = [ROLE_DRIVER]


class ReadOnlyForDriversMixin:
    """Restrict drivers to read-only access."""

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.user.role == ROLE_DRIVER and request.method not in [
            "GET",
            "HEAD",
            "OPTIONS",
        ]:
            raise PermissionDenied("Drivers have read-only access.")


<<<<<<< Updated upstream
# 🔹 Unified Maintenance Access
=======
>>>>>>> Stashed changes
class MaintenanceAccessMixin:
    """
    Maintenance access control:
    - Admin / Maintenancer: full access
    - Fleet Manager: read & create only
    """

    def check_permission(self, obj=None):
        user, method = self.request.user, self.request.method

        if user.role in [ROLE_ADMIN, ROLE_MAINTENANCE]:
            return True

        if user.role == ROLE_FLEET_MANAGER and method in [
            "GET",
            "HEAD",
            "OPTIONS",
            "POST",
        ]:
            return True

        raise PermissionDenied(
            "You don't have permission for this maintenance operation."
        )

    def get_object(self):
        obj = super().get_object()
        self.check_permission(obj)
        return obj


<<<<<<< Updated upstream
# 🔹 Unified Alerts & Analytics Access
=======
>>>>>>> Stashed changes
class AlertsAccessMixin(ScopedQuerysetMixin):
    """Filter alerts based on user role."""

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.role == ROLE_ADMIN:
            return qs
        if user.role == ROLE_FLEET_MANAGER and hasattr(user, "branch"):
            return qs.filter(branch=user.branch)
        if user.role == ROLE_MAINTENANCE:
            return qs.filter(alert_type__in=["maintenance", "breakdown", "service_due"])
        if user.role == ROLE_DRIVER:
            return qs.filter(driver=user)
        return qs.none()


class AnalyticsAccessMixin:
    """Define accessible data scope for analytics."""

    def get_analytics_scope(self):
        user = self.request.user

        if user.role == ROLE_ADMIN:
            return {}

        if user.role == ROLE_ORGANIZATION and hasattr(user, "organization"):
            return {"branch__organization": user.organization}

        if user.role == ROLE_FLEET_MANAGER and hasattr(user, "branch"):
            return {"branch": user.branch}

        if user.role == ROLE_MAINTENANCE:
            return {"report_type": "maintenance"}

        if user.role == ROLE_DRIVER:
            return {"driver": user}

        return {"pk__isnull": True}


<<<<<<< Updated upstream
# 🔹 Unified System & Financial Access
class AdminOnlyAccessMixin(RolePermissionMixin):
    """For system health, financial data, or admin dashboards"""

    required_roles = ADMIN_ROLES


# 🔹 Unified User & Trip Management
=======
>>>>>>> Stashed changes
class UserManagementAccessMixin:
    """Admin full control, Fleet Manager read-only."""

    def check_permission(self):
        user, method = self.request.user, self.request.method

        if user.role == ROLE_ADMIN:
            return True
        if user.role == ROLE_FLEET_MANAGER and method in ["GET", "HEAD", "OPTIONS"]:
            return True

        raise PermissionDenied("You don't have permission to manage users.")

    def dispatch(self, request, *args, **kwargs):
        self.check_permission()
        return super().dispatch(request, *args, **kwargs)


class TripAccessMixin(ScopedQuerysetMixin):
    """Unified trip access."""

    def check_trip_permission(self, trip):
        user = self.request.user

        if user.role == ROLE_ADMIN:
            return True

        if user.role == ROLE_ORGANIZATION and hasattr(user, "organization"):
            if trip.branch.organization == user.organization:
                return True

        if user.role == ROLE_FLEET_MANAGER and hasattr(user, "branch"):
            if trip.branch == user.branch:
                return True

        if user.role == ROLE_DRIVER and getattr(trip, "driver", None) == user:
            return True

        raise PermissionDenied("Access denied.")


<<<<<<< Updated upstream
# 🔹 Helper Decorators & Utilities
=======
# === DECORATORS ===
>>>>>>> Stashed changes
def role_required(*roles):
    """Decorator for function-based views enforcing role access."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return Response(
                    {"detail": "Authentication required."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if user.role not in roles:
                return Response(
                    {"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN
                )
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def user_can_access_vehicle(user, vehicle):
<<<<<<< Updated upstream
    if "admin" == ROLE_ADMIN:
        #  if request.user == ROLE_ADMIN:
=======
    """Check if user can access given vehicle."""
    if user.role == ROLE_ADMIN:
>>>>>>> Stashed changes
        return True
    if user.role == ROLE_ORGANIZATION and hasattr(vehicle, "branch"):
        return vehicle.branch.organization == getattr(user, "organization", None)
    if user.role == ROLE_FLEET_MANAGER:
        return getattr(vehicle, "branch", None) == getattr(user, "branch", None)
    if user.role == ROLE_DRIVER:
        return getattr(vehicle, "assigned_driver", None) == user
    return False


def user_can_access_trip(user, trip):
<<<<<<< Updated upstream
    if "admin" == ROLE_ADMIN:
        #  if request.user == ROLE_ADMIN:
=======
    """Check if user can access given trip."""
    if user.role == ROLE_ADMIN:
>>>>>>> Stashed changes
        return True
    if user.role == ROLE_ORGANIZATION and hasattr(trip, "branch"):
        return trip.branch.organization == getattr(user, "organization", None)
    if user.role == ROLE_FLEET_MANAGER:
        return getattr(trip, "branch", None) == getattr(user, "branch", None)
    if user.role == ROLE_DRIVER:
        return getattr(trip, "driver", None) == user
    return False


def get_accessible_branches(user):
<<<<<<< Updated upstream
    if "admin" == ROLE_ADMIN:
        #  if request.user == ROLE_ADMIN:
=======
    """Return branches visible to user."""
    if user.role == ROLE_ADMIN:
>>>>>>> Stashed changes
        return Branch.objects.all()
    if user.role == ROLE_ORGANIZATION and hasattr(user, "organization"):
        return Branch.objects.filter(organization=user.organization)
    if user.role in [
        ROLE_FLEET_MANAGER,
        ROLE_MAINTENANCE,
        ROLE_BRANCH_MANAGER,
    ] and hasattr(user, "branch"):
        return [user.branch]
    return []


def get_user_permissions_summary(user):
    """Frontend-friendly summary of user permissions."""
    return {
        "can_manage_users": "admin" == ROLE_ADMIN,
        # "can_manage_user": user.role == ROLE_ADMIN,
        # s": request.user == ROLE_ADMIN,
        "can_manage_vehicles": user.role in [ROLE_ADMIN, ROLE_FLEET_MANAGER],
        "can_manage_trips": user.role in [ROLE_ADMIN, ROLE_FLEET_MANAGER],
        "can_manage_maintenance": user.role
        in [ROLE_ADMIN, ROLE_MAINTENANCE, ROLE_FLEET_MANAGER],
        "can_view_reports": True,
        "can_view_analytics": user.role
        in [ROLE_ADMIN, ROLE_FLEET_MANAGER, ROLE_MAINTENANCE],
        "can_manage_alerts": user.role
        in [ROLE_ADMIN, ROLE_FLEET_MANAGER, ROLE_MAINTENANCE],
        "is_admin": user.role == ROLE_ADMIN,
        "is_fleet_manager": user.role == ROLE_FLEET_MANAGER,
        "is_driver": user.role == ROLE_DRIVER,
        "is_maintenance_supervisor": user.role == ROLE_MAINTENANCE,
    }
