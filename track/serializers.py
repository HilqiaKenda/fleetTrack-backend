from rest_framework import serializers
from django.db import transaction
from django.contrib.gis.geos import Point
from user.models import Carrier, Driver
from .models import Location, Vehicle, Trip, TripEvent
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


class VehicleSerializer(serializers.ModelSerializer):
    # carrier_name = serializers.CharField(source="carrier.name", read_only=True)

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
            "branch",
            # "carrier",
            # "carrier_name",
            "created_at",
        ]

class TripEventSerializer(serializers.ModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = TripEvent
        fields = [
            "id",
            "event_type",
            "timestamp",
            "duration",
            "miles_driven",
            "notes",
            "event_address",
            "event_location",
            "latitude",
            "longitude",
            "created_at",
            "updated_at",
        ]

    def get_latitude(self, obj):
        return obj.event_location.y if obj.event_location else None

    def get_longitude(self, obj):
        return obj.event_location.x if obj.event_location else None
    

class TripEventCreateSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=True, required=False)
    longitude = serializers.FloatField(write_only=True, required=False)

    class Meta:
        model = TripEvent
        fields = [
            "event_type",
            "timestamp",
            "duration",
            "miles_driven",
            "notes",
            "event_address",
            "latitude",
            "longitude",
        ]

    def create(self, validated_data):
        lat = validated_data.pop("latitude", None)
        lng = validated_data.pop("longitude", None)

        if lat is not None and lng is not None:
            validated_data["event_location"] = Point(lng, lat)

        return TripEvent.objects.create(**validated_data)


class TripSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source="driver.full_name", read_only=True)
    co_driver_name = serializers.CharField(source="co_driver.full_name", read_only=True)
    vehicle_info = serializers.CharField(source="vehicle.truck_number", read_only=True)

    cycle_hours_used = serializers.ReadOnlyField()
    events = TripEventSerializer(many=True, read_only=True)
    events_count = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = [
            "id",
            "date",
            "time",
            "driver",
            "driver_name",
            "co_driver",
            "co_driver_name",
            "vehicle",
            "vehicle_info",
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
            "status",
            "events",
            "events_count",
            "address",
            "origin_location",
            "destinaton_address",
            "destination_location",
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



class TripCreateSerializer(serializers.ModelSerializer):
    # truck_number = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Trip
        fields = [
            "date",
            "time",
            "driver",
            "co_driver",
            "vehicle",
            "shipper_and_commodity",
            "cycle_rule",
            "remarks",
            # "truck_number",
            "address",
            "origin_location",
            "destinaton_address",
            "destination_location",
        ]

    @transaction.atomic
    def create(self, validated_data):
        truck_number = validated_data.pop("truck_number", None)

        if truck_number and not validated_data.get("vehicle"):
            vehicle = Vehicle.objects.filter(truck_number=truck_number).first()
            if not vehicle:
                raise serializers.ValidationError(
                    {"truck_number": "Vehicle not found"}
                )
            validated_data["vehicle"] = vehicle

        trip = Trip.objects.create(**validated_data)
        return trip
    

class SearchResultsSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = serializers.ListField()


class SearchResponseSerializer(serializers.Serializer):
    status = serializers.BooleanField()
    query = serializers.CharField()
    page = serializers.IntegerField()

    drivers = SearchResultsSerializer()
    carriers = SearchResultsSerializer()
    trucks = SearchResultsSerializer()

class FleetDashboardSerializer(serializers.Serializer):
    total_vehicles = serializers.IntegerField()
    active_vehicles = serializers.IntegerField()
    booked_vehicles = serializers.IntegerField()
    maintenance_vehicles = serializers.IntegerField()

