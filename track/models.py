from django.utils import timezone
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Location(models.Model):
    """Normalized location model - one record per unique location"""

    address = models.CharField(max_length=255, unique=True)
    latitude = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text="Latitude coordinate",
    )
    longitude = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text="Longitude coordinate",
    )

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


class Driver(models.Model):
    """Driver information"""

    driver_initial = models.CharField(max_length=10, unique=True)
    full_name = models.CharField(max_length=255)
    license_number = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.driver_initial} - {self.full_name}"


class Carrier(models.Model):
    """Carrier/Company information"""

    name = models.CharField(max_length=255, unique=True)
    dot_number = models.CharField(max_length=20, unique=True, blank=True)
    mc_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Vehicle(models.Model):
    """Vehicle/Truck information"""

    truck_number = models.CharField(max_length=50, unique=True)
    make = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=50, blank=True)
    year = models.PositiveIntegerField(blank=True, null=True)
    vin = models.CharField(max_length=17, unique=True, blank=True)
    license_plate = models.CharField(max_length=20, blank=True)
    carrier = models.ForeignKey(
        Carrier, on_delete=models.CASCADE, related_name="vehicles"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.truck_number} - {self.make} {self.model}"


class Trip(models.Model):
    """Main trip record"""

    CYCLE_RULE_CHOICES = [("70hr/8day", "70hr/8day"), ("60hr/7day", "60hr/7day")]

    date = models.DateField()

    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name="trips")
    co_driver = models.ForeignKey(
        Driver,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="co_driver_trips",
    )
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="trips")

    shipper_and_commodity = models.CharField(max_length=255, blank=True)
    cycle_rule = models.CharField(
        max_length=20, choices=CYCLE_RULE_CHOICES, default="70hr/8day"
    )

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def cycle_hours_used(self):
        """Calculate total cycle hours (driving + on duty)"""
        return self.total_driving_hours + self.total_on_duty_hours

    @property
    def origin_location(self):
        """Get the first location of the trip"""
        first_event = self.events.order_by("timestamp").first()
        return first_event.location if first_event else None

    @property
    def destination_location(self):
        """Get the final destination of the trip"""
        last_driving_event = (
            self.events.filter(event_type__in=["driving_start", "driving_end"])
            .order_by("-timestamp")
            .first()
        )
        return last_driving_event.location if last_driving_event else None

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
        ("other", "Other"),
    ]

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="events")
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="trip_events"
    )

    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    timestamp = models.DateTimeField()
    duration = models.FloatField(
        default=0.0, help_text="Duration in hours", validators=[MinValueValidator(0)]
    )

    miles_driven = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0)],
        help_text="Miles driven during this event",
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["trip", "timestamp"]),
            models.Index(fields=["event_type", "timestamp"]),
            models.Index(fields=["location", "timestamp"]),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.trip.calculate_totals()

    def __str__(self):
        return f"{self.trip.id} - {self.get_event_type_display()} at {self.location.address}"
