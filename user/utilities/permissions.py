# permissions.py
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework import status
from functools import wraps
from user.models import Branch


# -------------------------------
# 🔹 Central Role Definitions
# -------------------------------
ROLE_ADMIN = "admin"
ROLE_FLEET_MANAGER = "fleet-manager"
ROLE_MAINTENANCE = "Maintenancer"
ROLE_DRIVER = "driver"
ROLE_BRANCH_MANAGER = "branch-manager"

ADMIN_ROLES = [ROLE_ADMIN]
MANAGER_ROLES = [ROLE_ADMIN, ROLE_FLEET_MANAGER]
MAINTENANCE_ROLES = [ROLE_ADMIN, ROLE_MAINTENANCE]
ALL_ROLES = [ROLE_ADMIN, ROLE_FLEET_MANAGER, ROLE_MAINTENANCE, ROLE_DRIVER]


# -------------------------------
# 🔹 Generic DRF Permission
# -------------------------------
class RolePermission(BasePermission):
    """
    Generic permission that checks if user has one of the required roles.
    Usage:
        permission_classes = [RolePermission(['admin', 'fleet-manager'])]
    """

    def __init__(self, allowed_roles=None):
        self.allowed_roles = allowed_roles or []

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and (not self.allowed_roles or request.user.role in self.allowed_roles)
        )

    @classmethod
    def for_roles(cls, roles):
        """
        Create a new permission subclass for the given roles.
        Example:
            RolePermission.for_roles(['admin', 'driver'])
        """

        class _RolePermission(cls):
            allowed_roles = roles

        # Give it a unique name for clarity in DRF browsable API and debugging
        _RolePermission.__name__ = f"RolePermission_{'_'.join(roles)}"
        return _RolePermission


# -------------------------------
# 🔹 Unified Role-Based Mixin
# -------------------------------
class RolePermissionMixin:
    """Reusable mixin to restrict access by role"""

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


# -------------------------------
# 🔹 Unified Data Filtering Mixin
# -------------------------------
class ScopedQuerysetMixin:
    """
    Automatically filter data based on user role:
    - Admin: all data
    - Fleet Manager & Maintenancer: own branch
    - Driver: own records
    """

    branch_field = "branch"
    driver_field = "driver"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.role == ROLE_ADMIN:
            return qs

        if user.role in [ROLE_FLEET_MANAGER, ROLE_MAINTENANCE]:
            if hasattr(user, "branch") and user.branch:
                return qs.filter(**{self.branch_field: user.branch})
            return qs.none()

        if user.role == ROLE_DRIVER:
            if hasattr(qs.model, self.driver_field):
                return qs.filter(**{self.driver_field: user})
            if hasattr(qs.model, "assigned_driver"):
                return qs.filter(assigned_driver=user)

        return qs.none()


# -------------------------------
# 🔹 Specialized Mixins
# -------------------------------
class AdminOnlyMixin(RolePermissionMixin):
    required_roles = ADMIN_ROLES


class FleetManagerMixin(RolePermissionMixin):
    required_roles = MANAGER_ROLES


class MaintenanceSupervisorMixin(RolePermissionMixin):
    required_roles = MAINTENANCE_ROLES


class DriverMixin(RolePermissionMixin):
    required_roles = [ROLE_DRIVER]


class ReadOnlyForDriversMixin:
    """Drivers have read-only access"""

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.user.role == ROLE_DRIVER and request.method not in [
            "GET",
            "HEAD",
            "OPTIONS",
        ]:
            raise PermissionDenied("Drivers have read-only access.")


# -------------------------------
# 🔹 Unified Maintenance Access
# -------------------------------
class MaintenanceAccessMixin:
    """
    Unified maintenance access control:
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


# -------------------------------
# 🔹 Unified Alerts & Analytics Access
# -------------------------------
class AlertsAccessMixin(ScopedQuerysetMixin):
    """Filter alerts based on user role"""

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.role == ROLE_ADMIN:
            return qs

        if user.role == ROLE_FLEET_MANAGER:
            return (
                qs.filter(branch=user.branch) if hasattr(user, "branch") else qs.none()
            )

        if user.role == ROLE_MAINTENANCE:
            return qs.filter(alert_type__in=["maintenance", "breakdown", "service_due"])

        if user.role == ROLE_DRIVER:
            return qs.filter(driver=user)

        return qs.none()


class AnalyticsAccessMixin:
    """Define accessible data scope for analytics"""

    def get_analytics_scope(self):
        user = self.request.user

        if user.role == ROLE_ADMIN:
            return {}

        if user.role == ROLE_FLEET_MANAGER:
            return (
                {"branch": user.branch}
                if hasattr(user, "branch")
                else {"branch__isnull": True}
            )

        if user.role == ROLE_MAINTENANCE:
            return {"report_type": "maintenance"}

        if user.role == ROLE_DRIVER:
            return {"driver": user}

        return {"pk__isnull": True}


# -------------------------------
# 🔹 Unified System & Financial Access
# -------------------------------
class AdminOnlyAccessMixin(RolePermissionMixin):
    """For system health, financial data, or admin dashboards"""

    required_roles = ADMIN_ROLES


# -------------------------------
# 🔹 Unified User & Trip Management
# -------------------------------
class UserManagementAccessMixin:
    """Admin full control, Fleet Manager read-only"""

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
    """Unified trip access"""

    def check_trip_permission(self, trip):
        user = self.request.user

        if user.role == ROLE_ADMIN:
            return True

        if user.role == ROLE_FLEET_MANAGER:
            if hasattr(user, "branch") and trip.branch == user.branch:
                return True
            raise PermissionDenied("You can only manage trips within your branch.")

        if user.role == ROLE_DRIVER:
            if hasattr(trip, "driver") and trip.driver == user:
                return True
            raise PermissionDenied("Drivers cannot modify other trips.")

        raise PermissionDenied("Access denied.")


# -------------------------------
# 🔹 Helper Decorators & Utilities
# -------------------------------
def role_required(*roles):
    """Decorator for function-based views"""

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
                    {"detail": "You do not have permission to access this resource."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def user_can_access_vehicle(user, vehicle):
    if user.role == ROLE_ADMIN:
        return True
    if user.role == ROLE_FLEET_MANAGER:
        return hasattr(vehicle, "branch") and vehicle.branch == getattr(
            user, "branch", None
        )
    if user.role == ROLE_DRIVER:
        return hasattr(vehicle, "assigned_driver") and vehicle.assigned_driver == user
    return False


def user_can_access_trip(user, trip):
    if user.role == ROLE_ADMIN:
        return True
    if user.role == ROLE_FLEET_MANAGER:
        return hasattr(trip, "branch") and trip.branch == getattr(user, "branch", None)
    if user.role == ROLE_DRIVER:
        return hasattr(trip, "driver") and trip.driver == user
    return False


def get_accessible_branches(user):
    if user.role == ROLE_ADMIN:
        return Branch.objects.all()
    if user.role in [ROLE_FLEET_MANAGER, ROLE_MAINTENANCE] and hasattr(user, "branch"):
        return [user.branch]
    return []


def get_user_permissions_summary(user):
    """Frontend-friendly summary of user permissions"""
    return {
        "can_manage_users": user.role == ROLE_ADMIN,
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
