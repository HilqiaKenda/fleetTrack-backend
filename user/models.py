from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.gis.db import models as gps_model
from django.utils.translation import gettext_lazy

# from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Custom manager for the User model."""

    def create_user(self, email, username, role, password=None, **extra_fields):
        """Create and return a regular user."""
        if not email:
            raise ValueError("The Email field is required.")
        if not username:
            raise ValueError("The Username field is required.")
        if not role:
            raise ValueError("The Role field is required.")

        email = self.normalize_email(email)

        valid_roles = [r[0] for r in User.ROLE_CHOICES]
        if role not in valid_roles:
            raise ValueError(
                f"Invalid role '{role}'. Valid roles are: {', '.join(valid_roles)}"
            )

        user = self.model(email=email, username=username, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        """Create and return a superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        role = "admin"

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, username, role, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model supporting email and role-based accounts."""

    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("organization", "Organization"),
        ("branch-manager", "Branch Manager"),
        ("fleet-manager", "Fleet Manager"),
        ("maintenancer", "Maintenancer"),
        ("driver", "Driver"),
    ]
    first_name = models.CharField(max_length=50, null=False, blank=False)
    last_name = models.CharField(max_length=50, null=False, blank=False)
    username = models.CharField(max_length=255, unique=True)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default="driver",
        help_text=gettext_lazy("The role of the user in the system."),
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Attach the manager
    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "users"
        verbose_name = gettext_lazy("user")
        verbose_name_plural = gettext_lazy("users")
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["username"]),
        ]

    def __str__(self):
        return f"{self.username} ({self.role})"

    def get_branches(self):
        """Return branches this user manages or is assigned to."""
        from .models import Branch

        if self.role in ["fleet-manager", "Maintenancer", "branch-manager"]:
            return Branch.objects.filter(branch_managers__user=self)
        return Branch.objects.filter(
            staff_assignments__user=self, staff_assignments__is_active=True
        )

    def get_primary_branch(self):
        """Return the primary branch for this user."""
        if self.primary_branch:
            return self.primary_branch

        primary_managed = getattr(self, "managed_branches", None)
        if primary_managed and primary_managed.filter(is_primary=True).exists():
            return primary_managed.filter(is_primary=True).first().branch

        primary_assignment = getattr(self, "branch_assignments", None)
        if primary_assignment and primary_assignment.filter(is_active=True).exists():
            return primary_assignment.filter(is_active=True).first().branch

        return None

    def can_access_branch(self, branch):
        """Check whether this user can access a specific branch."""
        if self.role == "admin":
            return True
        if self.role in ["fleet-manager", "Maintenancer", "branch-manager"]:
            return (
                getattr(self, "managed_branches", [])
                .filter(branch=branch, is_active=True)
                .exists()
            )
        return (
            getattr(self, "branch_assignments", [])
            .filter(branch=branch, is_active=True)
            .exists()
        )


class UserActivityLog(models.Model):
    """Track user actions for audit"""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="activity_logs"
    )
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=50)
    resource_id = models.IntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    device_info = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_activity_logs"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.action} at {self.timestamp}"


class Organization(models.Model):
    """
    Represents a top-level organization/company entity.
    Each organization can own multiple branches, vehicles, and users.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("inactive", "Inactive"),
        ("banned", "Banned"),
    ]

    name = models.CharField(
        max_length=255, unique=True, help_text=gettext_lazy("Organization name")
    )
    code = models.CharField(
        max_length=10,
        unique=True,
        help_text=gettext_lazy("Unique short code identifier (e.g., ORG001, TFC, KLM)"),
    )
    registration_number = models.CharField(
        max_length=100,
        blank=True,
        help_text=gettext_lazy("Company registration or tax number"),
    )
    email = models.EmailField(blank=True, null=True)
    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message=gettext_lazy(
            "Phone number must be in format: '+999999999'. Up to 15 digits allowed."
        ),
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        help_text=gettext_lazy("Primary contact number"),
    )
    address = models.TextField(
        blank=True, help_text=gettext_lazy("Head office address")
    )
    location = gps_model.PointField(
        null=True, blank=True, geography=True, spatial_index=True
    )
    website = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to="organization_logos/", null=True, blank=True)

    # Operational details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    industry = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organizations"
        ordering = ["name"]
        verbose_name = gettext_lazy("Organization")
        verbose_name_plural = gettext_lazy("Organizations")
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["code"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_branch_count(self):
        """Return total branches under this organization."""
        return self.branches.count()

    def get_user_count(self):
        """Return total users under this organization."""
        return self.users.count()

    def get_active_branches(self):
        """Return all active branches for this organization."""
        return self.branches.filter(status="active")


class Carrier(models.Model):
    """Carrier/Company information"""

    name = models.CharField(max_length=255, unique=True)
    dot_number = models.CharField(max_length=20, unique=True, blank=True)
    mc_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    location = gps_model.PointField(
        null=True, blank=True, geography=True, spatial_index=True
    )
    phone = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "carriers"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Branch(models.Model):
    """
    Branch/Location model for managing different fleet locations
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("maintenance", "Under Maintenance"),
    ]

    organization = models.ForeignKey(
        "Organization",
        on_delete=models.CASCADE,
        related_name="branches",
        default=0,
        help_text=gettext_lazy("The organization this branch belongs to."),
    )
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(
        max_length=10, unique=True, help_text="Short code for branch (e.g., KLA, MBS)"
    )

    # Location details
    address = models.TextField()
    location = gps_model.PointField(
        null=True, blank=True, geography=True, spatial_index=True
    )
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default="Uganda")

    # Contact information
    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17)
    email = models.EmailField()

    # Coordinates for mapping
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude coordinate",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude coordinate",
    )

    # Operational details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    capacity = models.PositiveIntegerField(
        default=0, help_text="Maximum number of vehicles this branch can handle"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "branches"
        ordering = ["name"]
        verbose_name_plural = "Branches"
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["status"]),
            models.Index(fields=["city", "region"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_driver_count(self):
        """Get total number of drivers assigned to this branch"""
        return self.drivers.count()

    def get_vehicle_count(self):
        """Get total number of vehicles in this branch"""
        return self.vehicles.count()

    def get_active_vehicle_count(self):
        """Get number of active vehicles in this branch"""
        return self.vehicles.filter(is_active=True).count()

    def is_at_capacity(self):
        """Check if branch is at full capacity"""
        return self.get_vehicle_count() >= self.capacity if self.capacity > 0 else False


class BranchManager(models.Model):
    """
    Branch Manager model - Links users to branches with management roles
    A user can be a manager/supervisor of one or multiple branches
    """

    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="managed_branches",
        limit_choices_to={
            "role__in": ["fleet-manager", "Maintenancer", "branch-manager"]
        },
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="branch_managers"
    )

    # Role-specific permissions at branch level
    ROLE_CHOICES = [
        ("manager", "Branch Manager"),
        ("supervisor", "Branch Supervisor"),
        ("maintenance_lead", "Maintenance Lead"),
    ]

    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default="manager")

    # Permissions
    can_approve_trips = models.BooleanField(default=True)
    can_assign_drivers = models.BooleanField(default=True)
    can_manage_vehicles = models.BooleanField(default=True)
    can_approve_maintenance = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=True)

    # Assignment details
    assigned_date = models.DateField(auto_now_add=True)
    is_primary = models.BooleanField(
        default=True, help_text="Is this the primary branch for this manager?"
    )
    is_active = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(
        blank=True, help_text="Additional notes about this assignment"
    )

    class Meta:
        db_table = "branch_managers"
        ordering = ["-is_primary", "branch__name"]
        unique_together = ["user", "branch"]
        verbose_name = "Branch Manager"
        verbose_name_plural = "Branch Managers"
        indexes = [
            models.Index(fields=["user", "branch"]),
            models.Index(fields=["is_active", "is_primary"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.branch.name} ({self.role})"

    def clean(self):
        """Validate branch manager assignment"""
        # Ensure user has appropriate role
        if self.user.role not in ["fleet-manager", "Maintenancer", "branch-manager"]:
            raise ValidationError(
                {
                    "user": "Only Fleet Managers, Maintenance Supervisors, or Branch Managers can be assigned to branches."
                }
            )

        # Maintenance leads should have maintenance approval permission
        if self.role == "maintenance_lead" and not self.can_approve_maintenance:
            self.can_approve_maintenance = True

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_managed_vehicles(self):
        """Get all vehicles under this manager's branch"""
        return self.branch.vehicles.all()

    def get_assigned_drivers(self):
        """Get all drivers assigned to this branch"""
        from .models import Driver

        return Driver.objects.filter(
            user__managed_branches__branch=self.branch, user__role="driver"
        )


class BranchAssignment(models.Model):
    """
    Assignment of drivers and other staff to branches
    Separate from BranchManager for regular staff assignments
    """

    user = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="branch_assignments"
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="staff_assignments"
    )

    # Assignment details
    assignment_type = models.CharField(
        max_length=50,
        choices=[
            ("permanent", "Permanent"),
            ("temporary", "Temporary"),
            ("on_loan", "On Loan"),
        ],
        default="permanent",
    )

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "branch_assignments"
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["user", "branch", "is_active"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.user.username} assigned to {self.branch.name}"

    def clean(self):
        """Validate assignment dates"""
        if self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": "End date must be after start date."})

    def is_current(self):
        """Check if assignment is currently active"""
        from datetime import date

        today = date.today()

        if not self.is_active:
            return False

        if self.start_date > today:
            return False

        if self.end_date and self.end_date < today:
            return False

        return True


class Driver(models.Model):
    """Driver information"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="driver_profile",
    )
    driver_initial = models.CharField(max_length=10, unique=True)
    full_name = models.CharField(max_length=255)
    license_number = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="drivers")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "drivers"
        ordering = ["driver_initial"]

    def __str__(self):
        return f"{self.driver_initial} - {self.full_name}"


class DashboardCache(models.Model):
    """Cache frequently accessed dashboard data"""

    cache_key = models.CharField(max_length=255, unique=True)
    cache_data = models.JSONField()
    user_role = models.CharField(max_length=50)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dashboard_cache"
        indexes = [
            models.Index(fields=["cache_key", "user_role"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.cache_key} - {self.user_role}"
