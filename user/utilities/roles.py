from rest_framework.permissions import BasePermission
from functools import wraps
from rest_framework.response import Response
from rest_framework import status

from backend.user.models import Branch


class IsAdmin(BasePermission):
    """
    Permission for Admin role
    - Full system access
    - User management
    - System configuration
    - Fleet-wide analytics
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )


class IsFleetManager(BasePermission):
    """
    Permission for Fleet Manager role
    - Branch-level operations
    - Vehicle and driver management
    - Trip monitoring
    - Alert handling
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "fleet-manager"
        )


class IsDriver(BasePermission):
    """
    Permission for Driver role
    - View assigned trips
    - Track own performance
    - View vehicle info
    - Report issues
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "driver"
        )


class IsMaintenanceSupervisor(BasePermission):
    """
    Permission for Maintenance Supervisor role
    - Maintenance scheduling
    - Vehicle service tracking
    - Downtime analytics
    - Issue management
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "Maintenancer"
        )


class IsAdminOrFleetManager(BasePermission):
    """
    Permission for Admin or Fleet Manager
    - Combined permissions for operational oversight
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ["admin", "fleet-manager"]
        )


class IsAdminOrMaintenanceSupervisor(BasePermission):
    """
    Permission for Admin or Maintenance Supervisor
    - Maintenance and repair management
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ["admin", "Maintenancer"]
        )


class CanManageUsers(BasePermission):
    """
    Permission to manage users (Admin only)
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        if request.user.role == "admin":
            return True

        # Fleet managers can view users but not create/delete admins
        if request.user.role == "fleet-manager":
            return request.method in ["GET", "HEAD", "OPTIONS"]

        return False


class CanManageVehicles(BasePermission):
    """
    Permission to manage vehicles
    - Admin: Full access
    - Fleet Manager: Branch vehicles only
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ["admin", "fleet-manager"]
        )

    def has_object_permission(self, request, view, obj):
        if request.user.role == "admin":
            return True

        # Fleet managers can only manage vehicles in their branch
        if request.user.role == "fleet-manager":
            # Assuming vehicle has a branch field and user has branch assignment
            return (
                hasattr(obj, "branch")
                and hasattr(request.user, "branch")
                and obj.branch == request.user.branch
            )

        return False


class CanManageTrips(BasePermission):
    """
    Permission to manage trips
    - Admin: All trips
    - Fleet Manager: Branch trips
    - Driver: View own trips only
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.role == "admin":
            return True

        if request.user.role == "fleet-manager":
            # Fleet managers manage trips in their branch
            return (
                hasattr(obj, "branch")
                and hasattr(request.user, "branch")
                and obj.branch == request.user.branch
            )

        if request.user.role == "driver":
            # Drivers can only view their own trips
            if request.method in ["GET", "HEAD", "OPTIONS"]:
                return hasattr(obj, "driver") and obj.driver == request.user
            return False

        return False


class CanManageMaintenance(BasePermission):
    """
    Permission to manage maintenance
    - Admin: Full access
    - Maintenance Supervisor: Full maintenance operations
    - Fleet Manager: View and create maintenance requests
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ["admin", "Maintenancer", "fleet-manager"]
        )

    def has_object_permission(self, request, view, obj):
        if request.user.role in ["admin", "Maintenancer"]:
            return True

        if request.user.role == "fleet-manager":
            # Fleet managers can view and request maintenance
            if request.method in ["GET", "HEAD", "OPTIONS", "POST"]:
                return True
            return False

        return False


class CanViewReports(BasePermission):
    """
    Permission to view reports
    - Admin: All reports
    - Fleet Manager: Branch reports
    - Maintenance Supervisor: Maintenance reports
    - Driver: Own performance reports
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user_role = request.user.role

        if user_role == "admin":
            return True

        if user_role == "fleet-manager":
            # Access to branch-level reports
            return (
                hasattr(obj, "branch")
                and hasattr(request.user, "branch")
                and obj.branch == request.user.branch
            )

        if user_role == "Maintenancer":
            # Access to maintenance reports only
            return hasattr(obj, "report_type") and obj.report_type == "maintenance"

        if user_role == "driver":
            # Access to own performance reports only
            return hasattr(obj, "driver") and obj.driver == request.user

        return False


class CanViewAnalytics(BasePermission):
    """
    Permission to view analytics dashboards
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # All roles except driver can view analytics
        return request.user.role in ["admin", "fleet-manager", "Maintenancer"]


class CanManageAlerts(BasePermission):
    """
    Permission to manage alerts
    - Admin: All alerts
    - Fleet Manager: Branch alerts
    - Maintenance Supervisor: Maintenance alerts
    - Driver: View own alerts
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user_role = request.user.role

        if user_role == "admin":
            return True

        if user_role == "fleet-manager":
            return (
                hasattr(obj, "branch")
                and hasattr(request.user, "branch")
                and obj.branch == request.user.branch
            )

        if user_role == "Maintenancer":
            # Can manage maintenance-related alerts
            return hasattr(obj, "alert_type") and obj.alert_type in [
                "maintenance",
                "breakdown",
                "service_due",
            ]

        if user_role == "driver":
            # Drivers can only view alerts related to their trips/vehicles
            if request.method in ["GET", "HEAD", "OPTIONS"]:
                return hasattr(obj, "driver") and obj.driver == request.user
            return False

        return False


# Decorator for function-based views
def role_required(*roles):
    """
    Decorator to check if user has required role
    Usage: @role_required('admin', 'fleet-manager')
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response(
                    {"detail": "Authentication required."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if request.user.role not in roles:
                return Response(
                    {"detail": "You do not have permission to access this resource."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


# Permission helper functions
def user_can_access_vehicle(user, vehicle):
    """Check if user can access a specific vehicle"""
    if user.role == "admin":
        return True

    if user.role == "fleet-manager":
        return (
            hasattr(vehicle, "branch")
            and hasattr(user, "branch")
            and vehicle.branch == user.branch
        )

    if user.role == "driver":
        return hasattr(vehicle, "assigned_driver") and vehicle.assigned_driver == user

    return False


def user_can_access_trip(user, trip):
    """Check if user can access a specific trip"""
    if user.role == "admin":
        return True

    if user.role == "fleet-manager":
        return (
            hasattr(trip, "branch")
            and hasattr(user, "branch")
            and trip.branch == user.branch
        )

    if user.role == "driver":
        return hasattr(trip, "driver") and trip.driver == user

    return False


def get_accessible_branches(user):
    """Get list of branches user can access"""
    if user.role == "admin":

        return Branch.objects.all()

    if user.role in ["fleet-manager", "Maintenancer"]:
        if hasattr(user, "branch"):
            return [user.branch]

    return []


def get_user_permissions_summary(user):
    """
    Return a summary of what a user can do
    Useful for frontend to show/hide UI elements
    """
    permissions = {
        "can_manage_users": user.role == "admin",
        "can_manage_vehicles": user.role in ["admin", "fleet-manager"],
        "can_manage_trips": user.role in ["admin", "fleet-manager"],
        "can_assign_drivers": user.role in ["admin", "fleet-manager"],
        "can_manage_maintenance": user.role
        in ["admin", "Maintenancer", "fleet-manager"],
        "can_view_all_reports": user.role == "admin",
        "can_view_branch_reports": user.role in ["admin", "fleet-manager"],
        "can_view_maintenance_reports": user.role in ["admin", "Maintenancer"],
        "can_view_own_reports": user.role == "driver",
        "can_manage_alerts": user.role in ["admin", "fleet-manager", "Maintenancer"],
        "can_view_analytics": user.role in ["admin", "fleet-manager", "Maintenancer"],
        "can_view_system_health": user.role == "admin",
        "can_view_financial_data": user.role == "admin",
        "can_manage_branches": user.role == "admin",
        "can_export_data": user.role in ["admin", "fleet-manager"],
        "is_admin": user.role == "admin",
        "is_fleet_manager": user.role == "fleet-manager",
        "is_driver": user.role == "driver",
        "is_maintenance_supervisor": user.role == "Maintenancer",
    }

    return permissions
