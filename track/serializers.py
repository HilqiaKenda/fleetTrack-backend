from rest_framework import serializers
from django.db import transaction
from .models import Location, Driver, Carrier, Vehicle, Trip, TripEvent
from time import timezone


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = [
            "id",
            "address",
            "latitude",
            "longitude",
            "city",
            "state",
            "country",
            "postal_code",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        # Check if location already exists
        address = validated_data.get("address")
        location, created = Location.objects.get_or_create(
            address=address, defaults=validated_data
        )
        return location


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = [
            "id",
            "driver_initial",
            "full_name",
            "license_number",
            "phone_number",
            "email",
            "created_at",
            "updated_at",
        ]


class CarrierSerializer(serializers.ModelSerializer):
    vehicles_count = serializers.SerializerMethodField()

    class Meta:
        model = Carrier
        fields = [
            "id",
            "name",
            "dot_number",
            "mc_number",
            "address",
            "phone",
            "vehicles_count",
            "created_at",
        ]

    def get_vehicles_count(self, obj):
        return obj.vehicles.count()


class VehicleSerializer(serializers.ModelSerializer):
    carrier_name = serializers.CharField(source="carrier.name", read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "truck_number",
            "make",
            "model",
            "year",
            "vin",
            "license_plate",
            "carrier",
            "carrier_name",
            "created_at",
        ]


class TripEventSerializer(serializers.ModelSerializer):
    location_address = serializers.CharField(source="location.address", read_only=True)
    location_data = LocationSerializer(source="location", read_only=True)

    class Meta:
        model = TripEvent
        fields = [
            "id",
            "event_type",
            "timestamp",
            "duration",
            "miles_driven",
            "notes",
            "location",
            "location_address",
            "location_data",
            "created_at",
            "updated_at",
        ]


class TripEventCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating trip events with nested location data"""

    location_data = serializers.DictField(write_only=True)

    class Meta:
        model = TripEvent
        fields = [
            "event_type",
            "timestamp",
            "duration",
            "miles_driven",
            "notes",
            "location_data",
        ]

    def create(self, validated_data):
        location_data = validated_data.pop("location_data")

        location_serializer = LocationSerializer(data=location_data)
        if location_serializer.is_valid():
            location = location_serializer.save()
        else:
            raise serializers.ValidationError(location_serializer.errors)

        trip_event = TripEvent.objects.create(location=location, **validated_data)
        return trip_event


class TripSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source="driver.full_name", read_only=True)
    co_driver_name = serializers.CharField(source="co_driver.full_name", read_only=True)
    vehicle_info = serializers.CharField(source="vehicle.truck_number", read_only=True)
    carrier_name = serializers.CharField(source="vehicle.carrier.name", read_only=True)

    cycle_hours_used = serializers.ReadOnlyField()
    origin_location = LocationSerializer(read_only=True)
    destination_location = LocationSerializer(read_only=True)

    events = TripEventSerializer(many=True, read_only=True)
    events_count = serializers.SerializerMethodField()

    current_location = serializers.SerializerMethodField()
    pickup_location = serializers.SerializerMethodField()
    dropoff_location = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = [
            "id",
            "date",
            "driver",
            "driver_name",
            "co_driver",
            "co_driver_name",
            "vehicle",
            "vehicle_info",
            "carrier_name",
            "shipper_and_commodity",
            "cycle_rule",
            "total_miles_driving",
            "total_mileage_today",
            "total_driving_hours",
            "total_on_duty_hours",
            "total_off_duty_hours",
            "total_sleeper_hours",
            "cycle_hours_used",
            "remarks",
            "is_completed",
            "events",
            "events_count",
            "origin_location",
            "destination_location",
            "current_location",
            "pickup_location",
            "dropoff_location",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "total_miles_driving",
            "total_driving_hours",
            "total_on_duty_hours",
            "total_off_duty_hours",
            "total_sleeper_hours",
            "cycle_hours_used",
        ]

    def get_events_count(self, obj):
        return obj.events.count()

    def get_current_location(self, obj):
        """For backward compatibility - return the most recent location"""
        latest_event = obj.events.order_by("-timestamp").first()
        if latest_event:
            return {
                "address": latest_event.location.address,
                "lat": latest_event.location.latitude,
                "lng": latest_event.location.longitude,
            }
        return None

    def get_pickup_location(self, obj):
        """For backward compatibility - return origin location"""
        if obj.origin_location:
            return {
                "address": obj.origin_location.address,
                "lat": obj.origin_location.latitude,
                "lng": obj.origin_location.longitude,
            }
        return None

    def get_dropoff_location(self, obj):
        """For backward compatibility - return destination location"""
        if obj.destination_location:
            return {
                "address": obj.destination_location.address,
                "lat": obj.destination_location.latitude,
                "lng": obj.destination_location.longitude,
            }
        return None


class TripCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating trips with initial event data"""

    initial_events = TripEventCreateSerializer(many=True, write_only=True)

    current_location = serializers.DictField(write_only=True, required=False)
    pickup_location = serializers.DictField(write_only=True, required=False)
    dropoff_location = serializers.DictField(write_only=True, required=False)

    driver_initial = serializers.CharField(write_only=True, required=False)
    carrier_name = serializers.CharField(write_only=True, required=False)
    truck_number = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Trip
        fields = [
            "date",
            "driver",
            "co_driver",
            "vehicle",
            "shipper_and_commodity",
            "cycle_rule",
            "total_mileage_today",
            "remarks",
            "initial_events",
            # Legacy fields
            "current_location",
            "pickup_location",
            "dropoff_location",
            "driver_initial",
            "carrier_name",
            "truck_number",
        ]

    @transaction.atomic
    def create(self, validated_data):
        initial_events_data = validated_data.pop("initial_events", [])

        legacy_locations = []
        if "current_location" in validated_data:
            legacy_locations.append(
                {
                    "location_data": validated_data.pop("current_location"),
                    "event_type": "other",
                    "timestamp": timezone.now(),
                    "notes": "Current location",
                }
            )

        if "pickup_location" in validated_data:
            legacy_locations.append(
                {
                    "location_data": validated_data.pop("pickup_location"),
                    "event_type": "loading",
                    "timestamp": timezone.now(),
                    "notes": "Pickup location",
                }
            )

        if "dropoff_location" in validated_data:
            legacy_locations.append(
                {
                    "location_data": validated_data.pop("dropoff_location"),
                    "event_type": "unloading",
                    "timestamp": timezone.now(),
                    "notes": "Dropoff location",
                }
            )

        driver_initial = validated_data.pop("driver_initial", None)
        carrier_name = validated_data.pop("carrier_name", None)
        truck_number = validated_data.pop("truck_number", None)

        if driver_initial and not validated_data.get("driver"):
            driver, _ = Driver.objects.get_or_create(
                driver_initial=driver_initial,
                defaults={
                    "full_name": driver_initial,
                    "license_number": f"LIC_{driver_initial}",
                },
            )
            validated_data["driver"] = driver

        if truck_number and not validated_data.get("vehicle"):
            if carrier_name:
                carrier, _ = Carrier.objects.get_or_create(
                    name=carrier_name,
                    defaults={"dot_number": f"DOT_{carrier_name[:10]}"},
                )
            else:
                carrier = Carrier.objects.first()
                if not carrier:
                    carrier = Carrier.objects.create(
                        name="Default Carrier", dot_number="DOT_DEFAULT"
                    )

            vehicle, _ = Vehicle.objects.get_or_create(
                truck_number=truck_number, defaults={"carrier": carrier}
            )
            validated_data["vehicle"] = vehicle

        trip = Trip.objects.create(**validated_data)

        all_events = initial_events_data + legacy_locations
        for event_data in all_events:
            event_serializer = TripEventCreateSerializer(data=event_data)
            if event_serializer.is_valid():
                event_serializer.save(trip=trip)

        return trip
