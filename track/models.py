from django.utils import timezone
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.gis.db import models as gps_model
from user.models import Carrier, Driver
import datetime
from django.utils.translation import gettext_lazy


class UserActivityLog(models.Model):
    """Track user actions for audit"""

    # user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=50)
    resource_id = models.IntegerField(null=True)
    ip_address = models.GenericIPAddressField()
    device_info = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)


class Location(models.Model):
    """Normalized location model - one record per unique location"""

    address = models.CharField(max_length=255)
    latitude = models.FloatField(validators=[MinValueValidator(-90), MaxValueValidator(90)], help_text="Latitude coordinate")
    longitude = models.FloatField(validators=[MinValueValidator(-180), MaxValueValidator(180)],help_text="Longitude coordinate")

    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=50, default="USA")
    postal_code = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["address"]
        indexes = [
            models.Index(fields=["address"]),
            models.Index(fields=["city", "state"]),
        ]

    def __str__(self):
        return self.address


class Vehicle(models.Model):
    """Vehicle/Truck information"""

    STATUS_CHOICES = [
        ("available", "Available"),
        ("maintainance", "Maintainance"),
        ("booked", "Booked"),
    ]

    truck_number = models.CharField(max_length=50, unique=True)
    make = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=50, blank=True)
    year = models.PositiveIntegerField(blank=True, null=True)
    vin = models.CharField(max_length=17, unique=True, blank=True)
    license_plate = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="active")
    branch = models.ForeignKey("user.Branch", on_delete=models.CASCADE, related_name="vehicles", default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.truck_number} - {self.make} {self.model}"


class Trip(models.Model):
    """Main trip record"""

    CYCLE_RULE_CHOICES = [("70hr/8day", "70hr/8day"), ("60hr/7day", "60hr/7day")]
    STATUS_CHOICES = [
        ("active", "active"),
        ("scheduled", "scheduled"),
        ("completed", "completed"),
        ("cancelled", "cancelled"),
    ]

    date = models.DateField(null=False, blank=False)
    time = models.TimeField(null=False, blank=False, default=datetime.time(0, 0))

    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name="trips")
    co_driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name="co_driver_trips")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="trips")
    shipper_and_commodity = models.CharField(max_length=255, blank=True)
    cycle_rule = models.CharField(max_length=20, choices=CYCLE_RULE_CHOICES, default="70hr/8day")

    address = models.TextField(blank=True, help_text=gettext_lazy("The origin office address"))
    origin_location = gps_model.PointField(null=True, blank=True, geography=True, spatial_index=True)
    destinaton_address = models.TextField(blank=True, help_text=gettext_lazy("The destination office address"))
    destination_location = gps_model.PointField(null=True, blank=True, geography=True, spatial_index=True)

    # Total trip metrics (calculated from trip events)
    total_miles_driving = models.FloatField(default=0.0)
    total_mileage_today = models.FloatField(default=0.0)
    total_driving_hours = models.FloatField(default=0.0)
    total_on_duty_hours = models.FloatField(default=0.0)
    total_off_duty_hours = models.FloatField(default=0.0)
    total_sleeper_hours = models.FloatField(default=0.0)

    # Additional information
    remarks = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def cycle_hours_used(self):
        """Calculate total cycle hours (driving + on duty)"""
        return self.total_driving_hours + self.total_on_duty_hours

    def calculate_totals(self):
        """Recalculate all totals based on trip events"""
        from django.db.models import Sum, Q

        hours_data = self.events.aggregate(
            driving_hours=Sum("duration", filter=Q(event_type="driving")),
            on_duty_hours=Sum("duration", filter=Q(event_type="on_duty")),
            off_duty_hours=Sum("duration", filter=Q(event_type="off_duty")),
            sleeper_hours=Sum("duration", filter=Q(event_type="sleeper")),
        )

        self.total_driving_hours = hours_data["driving_hours"] or 0.0
        self.total_on_duty_hours = hours_data["on_duty_hours"] or 0.0
        self.total_off_duty_hours = hours_data["off_duty_hours"] or 0.0
        self.total_sleeper_hours = hours_data["sleeper_hours"] or 0.0

        miles_data = self.events.filter(event_type="driving").aggregate(
            total_miles=Sum("miles_driven")
        )
        self.total_miles_driving = miles_data["total_miles"] or 0.0

        self.save()

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["date", "driver"]),
            models.Index(fields=["vehicle", "date"]),
        ]

    def __str__(self):
        return f"Trip {self.id} - {self.date} - {self.driver.driver_initial}"


class TripEvent(models.Model):
    """Individual events during a trip (stops, rests, driving segments)"""

    EVENT_TYPE_CHOICES = [
        ("driving", "Driving"),
        ("on_duty", "On Duty (Not Driving)"),
        ("off_duty", "Off Duty"),
        ("sleeper", "Sleeper Berth"),
        ("rest_break", "Rest Break"),
        ("fuel_stop", "Fuel Stop"),
        ("meal_break", "Meal Break"),
        ("inspection", "Vehicle Inspection"),
        ("loading", "Loading"),
        ("unloading", "Unloading"),
    ]

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="events")

    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    timestamp = models.DateTimeField()
    duration = models.FloatField(default=0.0, help_text="Duration in hours", validators=[MinValueValidator(0)])
    miles_driven = models.FloatField(default=0.0, validators=[MinValueValidator(0)], help_text="Miles driven during this event")
    notes = models.TextField(blank=True)

    # Event-specific address and location
    event_address = models.TextField(blank=True, help_text="Address of the event")
    event_location = gps_model.PointField(null=True, blank=True, geography=True, spatial_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["trip", "timestamp"]),
            models.Index(fields=["event_type", "timestamp"]),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.trip.calculate_totals()

    def __str__(self):
        return f"{self.trip.id} - {self.get_event_type_display()} at {self.event_address}"


class DashboardCache(models.Model):
    """Cache frequently accessed dashboard data"""

    cache_key = models.CharField(max_length=255, unique=True)
    cache_data = models.JSONField()
    user_role = models.CharField(max_length=50)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["cache_key", "user_role"]),
            models.Index(fields=["expires_at"]),
        ]


class AlertLog(models.Model):
    """Track all system alerts"""

    SEVERITY_CHOICES = [
        ("critical", "Critical"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=50)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    message = models.TextField()
    address = models.TextField(blank=True, help_text=gettext_lazy("The office address"))
    location = gps_model.PointField(null=True, blank=True, geography=True, spatial_index=True)
    is_resolved = models.BooleanField(default=False)
    
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey("user.User", on_delete=models.SET_NULL, null=True, related_name="resolved_alerts",)
    
    created_at = models.DateTimeField(auto_now_add=True)
