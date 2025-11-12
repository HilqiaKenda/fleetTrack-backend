from django.core.management.base import BaseCommand
from django.db import IntegrityError
from faker import Faker
from random import randint, uniform, choice
from django.utils import timezone
from datetime import timedelta, date

from track.models import Location, Vehicle, Trip, TripEvent
from user.models import Driver, Carrier, Branch, BranchManager, BranchAssignment, User

fake = Faker()


class Command(BaseCommand):
    help = "Generate full seed data for branches, vehicles, drivers, trips, and trip events"

    def add_arguments(self, parser):
        parser.add_argument(
            "--num_trips", type=int, default=100, help="Number of trips to generate"
        )
        parser.add_argument(
            "--num_branches", type=int, default=5, help="Number of branches to generate"
        )
        parser.add_argument("--num_vehicles_per_branch", type=int, default=10)
        parser.add_argument("--num_drivers", type=int, default=20)

    def handle(self, *args, **kwargs):
        num_trips = kwargs["num_trips"]
        num_branches = kwargs["num_branches"]
        num_vehicles_per_branch = kwargs["num_vehicles_per_branch"]
        num_drivers = kwargs["num_drivers"]

        self.stdout.write(self.style.SUCCESS("Generating Carriers..."))
        carriers = self.create_carriers(5)

        self.stdout.write(self.style.SUCCESS("Generating Branches..."))
        branches = self.create_branches(num_branches)

        self.stdout.write(self.style.SUCCESS("Generating Users and Drivers..."))
        drivers, driver_users = self.create_drivers(num_drivers, branches)

        self.stdout.write(self.style.SUCCESS("Generating Vehicles..."))
        vehicles = self.create_vehicles(branches, carriers, num_vehicles_per_branch)

        self.stdout.write(self.style.SUCCESS("Generating Locations..."))
        locations = self.create_locations(num_trips * 5)

        self.stdout.write(self.style.SUCCESS("Generating Trips..."))
        trips = self.create_trips(drivers, vehicles, num_trips)

        self.stdout.write(self.style.SUCCESS("Generating Trip Events..."))
        self.create_trip_events(trips, locations)

        self.stdout.write(self.style.SUCCESS("Seed data generation complete!"))

    # ----------------- Seeders -----------------
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

    def create_branches(self, num=5):
        branches = []
        ugandan_cities = [
            ("Kampala", 0.3476, 32.5825),
            ("Mbarara", -0.6003, 30.6583),
            ("Gulu", 2.7747, 32.2989),
            ("Jinja", 0.4244, 33.2040),
            ("Entebbe", 0.0565, 32.4635),
        ]
        for i in range(num):
            city = choice(ugandan_cities)
            lat_offset = uniform(-0.05, 0.05)
            lon_offset = uniform(-0.05, 0.05)
            branch = Branch(
                name=f"{city[0]} Branch {i+1}",
                code=f"{city[0][:3].upper()}{i+1}",
                address=fake.address(),
                city=city[0],
                region=fake.state(),
                country="Uganda",
                phone_number=fake.phone_number(),
                email=fake.company_email(),
                latitude=round(city[1] + lat_offset, 6),
                longitude=round(city[2] + lon_offset, 6),
                capacity=randint(5, 20),
                status="active",
            )
            branches.append(branch)
        Branch.objects.bulk_create(branches)
        return list(Branch.objects.all())

    #

    def create_drivers(self, num=20, branches=None):
        drivers = []
        driver_users = []
        for _ in range(num):
            full_name = fake.name()
            username = full_name.replace(" ", "").lower()
            email = fake.unique.email()
            user = User.objects.create_user(
                email=email, username=username, role="driver", password="password123"
            )

            # Assign a branch
            branch = choice(branches) if branches else None

            driver = Driver(
                user=user,
                driver_initial=fake.unique.bothify(text="D###"),
                full_name=full_name,
                license_number=fake.unique.bothify(text="LIC#####"),
                phone_number=fake.phone_number(),
                email=email,
                branch=branch,  # <-- assign branch directly
            )
            drivers.append(driver)
            driver_users.append(user)

            # Optional: keep BranchAssignment for history tracking
            if branch:
                BranchAssignment.objects.create(
                    user=user,
                    branch=branch,
                    assignment_type="permanent",
                    start_date=date.today() - timedelta(days=randint(1, 365)),
                    is_active=True,
                )

        Driver.objects.bulk_create(drivers)
        return drivers, driver_users

    def create_vehicles(self, branches, carriers, num_per_branch=10):
        vehicles = []
        for branch in branches:
            for _ in range(num_per_branch):
                vehicle = Vehicle(
                    truck_number=f"TRK-{randint(1000, 9999)}",
                    branch=branch,
                    carrier=choice(carriers),
                    license_plate=fake.unique.bothify(
                        text="U####"
                    ),  # Unique license plate
                    vin=fake.unique.vin(),  # Unique VIN
                    make=fake.company(),
                    model=fake.word(),
                    year=randint(2005, 2025),
                    status=choice(["active", "maintenance", "inactive"]),
                )
                vehicles.append(vehicle)

        # Bulk create vehicles and handle possible errors
        try:
            Vehicle.objects.bulk_create(vehicles)
            print(f"{len(vehicles)} vehicles created successfully.")
        except IntegrityError as e:
            print(f"Error creating vehicles: {e}")
            # Handle integrity errors if the bulk_create fails
            return []

        return vehicles

    def create_locations(self, num=100):
        locations = []
        ugandan_cities = [
            ("Kampala", 0.3476, 32.5825),
            ("Mbarara", -0.6003, 30.6583),
            ("Gulu", 2.7747, 32.2989),
            ("Jinja", 0.4244, 33.2040),
            ("Entebbe", 0.0565, 32.4635),
        ]
        for _ in range(num):
            city_data = choice(ugandan_cities)
            lat_offset = uniform(-0.05, 0.05)
            lon_offset = uniform(-0.05, 0.05)
            loc = Location(
                address=fake.street_address(),
                latitude=round(city_data[1] + lat_offset, 6),
                longitude=round(city_data[2] + lon_offset, 6),
                city=city_data[0],
                state=fake.state_abbr(),
                country="Uganda",
                postal_code=fake.postcode(),
            )
            locations.append(loc)
        Location.objects.bulk_create(locations, ignore_conflicts=True)
        return list(Location.objects.all())

    def create_trips(self, drivers, vehicles, num=10):
        trips = []
        if not vehicles:
            print("Error: No vehicles available for creating trips.")
            return []

        statuses = ["active", "assigned", "ongoing", "completed"]
        for _ in range(num):
            driver = choice(drivers)
            co_driver = choice(drivers) if randint(0, 3) == 0 else None
            vehicle = choice(vehicles)  # This will no longer throw IndexError
            trip_date = timezone.now().date() - timedelta(days=randint(0, 30))
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
        return list(Trip.objects.order_by("-created_at")[:num])

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
            num_events = randint(5, 15)
            timestamp = timezone.make_aware(
                timezone.datetime.combine(trip.date, timezone.datetime.min.time())
            )
            for _ in range(num_events):
                location = choice(locations)
                event_type = choice(event_types)
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
                else:
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
                timestamp += timedelta(hours=duration)
        TripEvent.objects.bulk_create(events)
        self.stdout.write(self.style.SUCCESS(f"Created {len(events)} trip events"))
