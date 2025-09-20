from django.core.management.base import BaseCommand
from faker import Faker
from random import randint, uniform, choice
from django.utils import timezone
from track.models import Location, Driver, Carrier, Vehicle, Trip, TripEvent

fake = Faker()


class Command(BaseCommand):
    help = "Generate seed data for Location, Driver, Carrier, Vehicle, Trip, and TripEvent models"

    def add_arguments(self, parser):
        parser.add_argument(
            "--num", type=int, default=10, help="Number of trips to generate"
        )

    def handle(self, *args, **kwargs):
        num_records = kwargs["num"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Starting seed data generation for {num_records} trips..."
            )
        )

        # Locations
        self.stdout.write(self.style.SUCCESS("Generating Locations..."))
        locations = self.create_locations(num_records * 5)

        # Drivers
        self.stdout.write(self.style.SUCCESS("Generating Drivers..."))
        drivers = self.create_drivers(num_records)

        # Carriers
        self.stdout.write(self.style.SUCCESS("Generating Carriers..."))
        carriers = self.create_carriers(num_records // 2 or 1)

        # Vehicles
        self.stdout.write(self.style.SUCCESS("Generating Vehicles..."))
        vehicles = self.create_vehicles(carriers, num_records)

        # Trips
        self.stdout.write(self.style.SUCCESS("Generating Trips..."))
        trips = self.create_trips(drivers, vehicles, num_records)

        # Trip Events
        self.stdout.write(self.style.SUCCESS("Generating Trip Events..."))
        self.create_trip_events(trips, locations)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed data generation complete! {num_records} trips created."
            )
        )

    def create_locations(self, num=100):
        locations = []
        for _ in range(num):
            address = fake.street_address()
            location = Location(
                address=address,
                latitude=round(uniform(-90, 90), 6),
                longitude=round(uniform(-180, 180), 6),
                city=fake.city(),
                state=fake.state_abbr(),
                country="USA",
                postal_code=fake.postcode(),
            )
            locations.append(location)
        Location.objects.bulk_create(locations, ignore_conflicts=True)
        return list(Location.objects.all())

    def create_drivers(self, num=20):
        drivers = []
        for _ in range(num):
            driver = Driver(
                driver_initial=fake.lexify(text="??").upper(),
                full_name=fake.name(),
                license_number=fake.unique.bothify(text="LIC#######"),
                phone_number=fake.phone_number(),
                email=fake.email(),
            )
            drivers.append(driver)
        Driver.objects.bulk_create(drivers, ignore_conflicts=True)
        return list(Driver.objects.all())

    def create_carriers(self, num=5):
        carriers = []
        for _ in range(num):
            carrier = Carrier(
                name=fake.company(),
                dot_number=fake.unique.bothify(text="DOT#####"),
                mc_number=fake.bothify(text="MC#####"),
                address=fake.address(),
                phone=fake.phone_number(),
            )
            carriers.append(carrier)
        Carrier.objects.bulk_create(carriers, ignore_conflicts=True)
        return list(Carrier.objects.all())

    def create_vehicles(self, carriers, num=20):
        vehicles = []
        for _ in range(num):
            carrier = choice(carriers)
            vehicle = Vehicle(
                truck_number=fake.unique.bothify(text="TRK-####"),
                make=fake.company(),
                model=fake.word().capitalize(),
                year=randint(2000, 2024),
                vin=fake.unique.bothify(text="VIN###########"),
                license_plate=fake.bothify(text="??-####"),
                carrier=carrier,
            )
            vehicles.append(vehicle)
        Vehicle.objects.bulk_create(vehicles, ignore_conflicts=True)
        return list(Vehicle.objects.all())

    def create_trips(self, drivers, vehicles, num=10):
        trips = []
        for _ in range(num):
            driver = choice(drivers)
            co_driver = choice(drivers) if randint(0, 1) else None
            vehicle = choice(vehicles)

            trip = Trip(
                date=fake.date_this_year(),
                driver=driver,
                co_driver=co_driver,
                vehicle=vehicle,
                shipper_and_commodity=fake.bs(),
                cycle_rule=choice(["70hr/8day", "60hr/7day"]),
                remarks=fake.text(max_nb_chars=200),
                is_completed=bool(randint(0, 1)),
            )
            trips.append(trip)
        Trip.objects.bulk_create(trips)
        return list(Trip.objects.all())

    def create_trip_events(self, trips, locations):
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
            num_events = randint(3, 10)
            timestamp = timezone.now()

            for _ in range(num_events):
                location = choice(locations)
                event_type = choice(event_types)
                duration = (
                    round(uniform(0.5, 5.0), 2)
                    if event_type in ["driving", "on_duty", "off_duty", "sleeper"]
                    else 0.0
                )
                miles_driven = (
                    round(uniform(10.0, 300.0), 2) if event_type == "driving" else 0.0
                )

                event = TripEvent(
                    trip=trip,
                    location=location,
                    event_type=event_type,
                    timestamp=timestamp,
                    duration=duration,
                    miles_driven=miles_driven,
                    notes=fake.text(max_nb_chars=100),
                )
                events.append(event)

                # Advance timestamp
                timestamp += timezone.timedelta(hours=max(duration, 1))

        TripEvent.objects.bulk_create(events)
