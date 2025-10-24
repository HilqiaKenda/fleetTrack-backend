from rest_framework.exceptions import PermissionDenied
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied


class RoleRequiredMixin:
    """
    Mixin to restrict access based on user roles
    Usage:
        class MyView(RoleRequiredMixin, APIView):
            required_roles = ['admin', 'fleet-manager']
    """

    required_roles = []

    def check_role_permission(self):
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        if not self.required_roles:
            return True

        if self.request.user.role not in self.required_roles:
            raise PermissionDenied(
                f"This action requires one of the following roles: {', '.join(self.required_roles)}"
            )

        return True

    def dispatch(self, request, *args, **kwargs):
        self.check_role_permission()
        return super().dispatch(request, *args, **kwargs)


class AdminOnlyMixin(RoleRequiredMixin):
    """Restrict access to Admin only"""

    required_roles = ["admin"]


class FleetManagerMixin(RoleRequiredMixin):
    """Restrict access to Fleet Manager and Admin"""

    required_roles = ["admin", "fleet-manager"]


class MaintenanceSupervisorMixin(RoleRequiredMixin):
    """Restrict access to Maintenance Supervisor and Admin"""

    required_roles = ["admin", "Maintenancer"]


class DriverMixin(RoleRequiredMixin):
    """Restrict access to Driver role"""

    required_roles = ["driver"]


class BranchManagerAccessMixin:
    """
    Mixin to filter querysets by user's branch access
    Automatically filters data based on user's branch assignment
    """

    branch_field = "branch"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Admin can see everything
        if user.role == "admin":
            return queryset

        # Fleet managers and maintenance supervisors see only their branch
        if user.role in ["fleet-manager", "Maintenancer"]:
            if hasattr(user, "branch") and user.branch:
                filter_kwargs = {self.branch_field: user.branch}
                return queryset.filter(**filter_kwargs)
            else:
                # No branch assigned, return empty queryset
                return queryset.none()

        # Drivers see only their own data
        if user.role == "driver":
            if hasattr(queryset.model, "driver"):
                return queryset.filter(driver=user)
            elif hasattr(queryset.model, "assigned_driver"):
                return queryset.filter(assigned_driver=user)

        return queryset.none()


class DriverOwnDataMixin:
    """
    Mixin to ensure drivers can only access their own data
    """

    driver_field = "driver"  # Override if your model uses different field name

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Non-drivers use parent queryset logic
        if user.role != "driver":
            return queryset

        # Drivers only see their own data
        filter_kwargs = {self.driver_field: user}
        return queryset.filter(**filter_kwargs)

    def get_object(self):
        obj = super().get_object()
        user = self.request.user

        # Drivers can only access their own objects
        if user.role == "driver":
            driver_value = getattr(obj, self.driver_field, None)
            if driver_value != user:
                raise PermissionDenied("You can only access your own data.")

        return obj


class ReadOnlyForDriversMixin:
    """
    Mixin to make views read-only for drivers
    Drivers can only GET, others can perform all operations
    """

    def check_permissions(self, request):
        super().check_permissions(request)

        if request.user.role == "driver":
            if request.method not in ["GET", "HEAD", "OPTIONS"]:
                raise PermissionDenied("Drivers have read-only access.")


class MaintenanceDataAccessMixin:
    """
    Mixin for maintenance-related data access
    - Admin: Full access
    - Maintenance Supervisor: Full maintenance operations
    - Fleet Manager: Read and create requests
    """

    def check_maintenance_permission(self, obj=None):
        user = self.request.user
        method = self.request.method

        # Admin has full access
        if user.role == "admin":
            return True

        # Maintenance supervisor has full access
        if user.role == "Maintenancer":
            return True

        # Fleet manager can view and create
        if user.role == "fleet-manager":
            if method in ["GET", "HEAD", "OPTIONS", "POST"]:
                return True
            raise PermissionDenied(
                "Fleet managers can only view and create maintenance requests."
            )

        raise PermissionDenied("You don't have permission to access maintenance data.")

    def get_object(self):
        obj = super().get_object()
        self.check_maintenance_permission(obj)
        return obj


class AlertAccessMixin:
    """
    Mixin for alert data access
    Filters alerts based on user role and permissions
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Admin sees all alerts
        if user.role == "admin":
            return queryset

        # Fleet manager sees branch alerts
        if user.role == "fleet-manager":
            if hasattr(user, "branch") and user.branch:
                return queryset.filter(branch=user.branch)
            return queryset.none()

        # Maintenance supervisor sees maintenance-related alerts
        if user.role == "Maintenancer":
            return queryset.filter(
                alert_type__in=["maintenance", "breakdown", "service_due"]
            )

        # Driver sees own alerts
        if user.role == "driver":
            return queryset.filter(driver=user)

        return queryset.none()


class AnalyticsAccessMixin:
    """
    Mixin for analytics and reporting access
    Ensures proper data scoping for analytics views
    """

    def get_analytics_scope(self):
        """
        Returns the scope of data user can access for analytics
        Returns: dict with filters to apply
        """
        user = self.request.user

        if user.role == "admin":
            return {}  # No filters, see everything

        if user.role == "fleet-manager":
            if hasattr(user, "branch") and user.branch:
                return {"branch": user.branch}
            return {"branch__isnull": True}  # Return empty results

        if user.role == "Maintenancer":
            # Maintenance supervisor sees maintenance data only
            return {"report_type": "maintenance"}

        if user.role == "driver":
            return {"driver": user}

        return {"pk__isnull": True}  # Return empty results


class FinancialDataAccessMixin:
    """
    Mixin for financial data access - Admin only
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        if request.user.role != "admin":
            raise PermissionDenied("Only administrators can access financial data.")

        return super().dispatch(request, *args, **kwargs)


class SystemHealthAccessMixin:
    """
    Mixin for system health and monitoring - Admin only
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        if request.user.role != "admin":
            raise PermissionDenied("Only administrators can access system health data.")

        return super().dispatch(request, *args, **kwargs)


class UserManagementAccessMixin:
    """
    Mixin for user management operations
    - Admin: Full access
    - Fleet Manager: Read-only access
    """

    def check_user_management_permission(self):
        user = self.request.user
        method = self.request.method

        if user.role == "admin":
            return True

        if user.role == "fleet-manager":
            if method in ["GET", "HEAD", "OPTIONS"]:
                return True
            raise PermissionDenied(
                "Fleet managers have read-only access to user management."
            )

        raise PermissionDenied("You don't have permission to manage users.")

    def dispatch(self, request, *args, **kwargs):
        self.check_user_management_permission()
        return super().dispatch(request, *args, **kwargs)


class TripManagementMixin:
    """
    Mixin for trip management with role-based access
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Admin sees all trips
        if user.role == "admin":
            return queryset

        # Fleet manager sees branch trips
        if user.role == "fleet-manager":
            if hasattr(user, "branch") and user.branch:
                return queryset.filter(branch=user.branch)
            return queryset.none()

        # Driver sees only their trips
        if user.role == "driver":
            return queryset.filter(driver=user)

        return queryset.none()

    def check_trip_permission(self, trip):
        """Check if user can modify a specific trip"""
        user = self.request.user

        if user.role == "admin":
            return True

        if user.role == "fleet-manager":
            if hasattr(trip, "branch") and hasattr(user, "branch"):
                if trip.branch == user.branch:
                    return True
            raise PermissionDenied("You can only manage trips in your branch.")

        if user.role == "driver":
            raise PermissionDenied("Drivers cannot modify trips.")

        return False
