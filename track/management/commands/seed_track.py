# management/commands/seed_track_data.py

from django.core.management.base import BaseCommand
from faker import Faker
from random import randint, uniform, choice
from django.utils import timezone
from datetime import timedelta

from track.models import Location, Vehicle, Trip, TripEvent
from user.models import Driver, Carrier, Branch


fake = Faker()


class Command(BaseCommand):
    help = "Generate seed data for Location, Trip, and TripEvent models"

    def add_arguments(self, parser):
        parser.add_argument(
            "--num", type=int, default=100, help="Number of trips to generate"
        )

    def handle(self, *args, **kwargs):
        num_records = kwargs["num"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Starting seed data generation for {num_records} trips..."
            )
        )

        # Check if we have necessary data
        drivers = list(Driver.objects.all())
        vehicles = list(Vehicle.objects.all())

        if not drivers:
            self.stdout.write(
                self.style.ERROR(
                    "No drivers found! Please run seed_admin_dashboard first."
                )
            )
            return

        if not vehicles:
            self.stdout.write(
                self.style.ERROR(
                    "No vehicles found! Please run seed_admin_dashboard first."
                )
            )
            return

        self.stdout.write(self.style.SUCCESS("Generating Locations..."))
        locations = self.create_locations(num_records * 5)

        self.stdout.write(self.style.SUCCESS("Generating Trips..."))
        trips = self.create_trips(drivers, vehicles, num_records)

        self.stdout.write(self.style.SUCCESS("Generating Trip Events..."))
        self.create_trip_events(trips, locations)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed data generation complete! {num_records} trips created."
            )
        )

    def create_locations(self, num=100):
        """Create location records"""
        locations = []
        ugandan_cities = [
            ("Kampala", 0.3476, 32.5825),
            ("Mbarara", -0.6003, 30.6583),
            ("Gulu", 2.7747, 32.2989),
            ("Jinja", 0.4244, 33.2040),
            ("Entebbe", 0.0565, 32.4635),
            ("Mbale", 1.0821, 34.1751),
            ("Lira", 2.2499, 32.8987),
            ("Fort Portal", 0.6710, 30.2750),
        ]

        for _ in range(num):
            city_data = choice(ugandan_cities)
            # Add some variation to coordinates
            lat_offset = uniform(-0.05, 0.05)
            lon_offset = uniform(-0.05, 0.05)

            location = Location(
                address=fake.street_address(),
                latitude=round(city_data[1] + lat_offset, 6),
                longitude=round(city_data[2] + lon_offset, 6),
                city=city_data[0],
                state=fake.state_abbr(),
                country="Uganda",
                postal_code=fake.postcode(),
            )
            locations.append(location)

        Location.objects.bulk_create(locations, ignore_conflicts=True)
        return list(Location.objects.all())

    def create_trips(self, drivers, vehicles, num=10):
        """Create trip records"""
        trips = []
        statuses = ["active", "assigned", "ongoing", "completed"]

        for _ in range(num):
            driver = choice(drivers)
            co_driver = choice(drivers) if randint(0, 3) == 0 else None  # 25% chance
            vehicle = choice(vehicles)

            # Generate a date within the last 30 days
            days_ago = randint(0, 30)
            trip_date = (timezone.now() - timedelta(days=days_ago)).date()

            is_completed = bool(randint(0, 1))
            status = "completed" if is_completed else choice(statuses)

            trip = Trip(
                date=trip_date,
                driver=driver,
                co_driver=co_driver,
                vehicle=vehicle,
                shipper_and_commodity=fake.company() + " - " + fake.word().capitalize(),
                cycle_rule=choice(["70hr/8day", "60hr/7day"]),
                remarks=fake.text(max_nb_chars=200) if randint(0, 2) == 0 else "",
                is_completed=is_completed,
                status=status,
            )
            trips.append(trip)

        Trip.objects.bulk_create(trips)

        # Fetch created trips to get IDs
        created_trips = list(Trip.objects.order_by("-created_at")[:num])
        return created_trips

    def create_trip_events(self, trips, locations):
        """Create trip events for each trip"""
        events = []
        event_types = [
            "driving",
            "on_duty",
            "off_duty",
            "sleeper",
            "rest_break",
            "fuel_stop",
            "meal_break",
            "inspection",
            "loading",
            "unloading",
            "other",
        ]

        for trip in trips:
            num_events = randint(5, 15)

            # Start from the trip date
            timestamp = timezone.make_aware(
                timezone.datetime.combine(trip.date, timezone.datetime.min.time())
            )

            for i in range(num_events):
                location = choice(locations)
                event_type = choice(event_types)

                # Generate realistic durations based on event type
                if event_type == "driving":
                    duration = round(uniform(1.0, 4.0), 2)
                    miles_driven = round(uniform(50.0, 250.0), 2)
                elif event_type in ["on_duty", "loading", "unloading"]:
                    duration = round(uniform(0.5, 2.0), 2)
                    miles_driven = 0.0
                elif event_type in ["off_duty", "sleeper"]:
                    duration = round(uniform(2.0, 10.0), 2)
                    miles_driven = 0.0
                elif event_type in ["rest_break", "meal_break"]:
                    duration = round(uniform(0.25, 1.0), 2)
                    miles_driven = 0.0
                else:  # fuel_stop, inspection, other
                    duration = round(uniform(0.25, 1.5), 2)
                    miles_driven = 0.0

                event = TripEvent(
                    trip=trip,
                    location=location,
                    event_type=event_type,
                    timestamp=timestamp,
                    duration=duration,
                    miles_driven=miles_driven,
                    notes=fake.text(max_nb_chars=100) if randint(0, 3) == 0 else "",
                )
                events.append(event)

                # Move timestamp forward
                timestamp += timedelta(hours=duration)

        TripEvent.objects.bulk_create(events)

        self.stdout.write(self.style.SUCCESS(f"Created {len(events)} trip events"))
