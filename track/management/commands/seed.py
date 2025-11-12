from django.core.management.base import BaseCommand
from faker import Faker
from random import randint, uniform, choice
from django.utils import timezone
from datetime import timedelta

from track.models import Location, Vehicle, Trip, TripEvent
from user.models import BranchAssignment, Driver, Carrier, Branch, User

fake = Faker()


class Command(BaseCommand):
    help = "Generate full seed data for carriers, branches, vehicles, drivers, trips, and trip events"

    def add_arguments(self, parser):
        parser.add_argument(
            "--num_trips", type=int, default=50, help="Number of trips to generate"
        )
        parser.add_argument(
            "--num_branches", type=int, default=5, help="Number of branches to generate"
        )
        parser.add_argument(
            "--num_drivers", type=int, default=20, help="Number of drivers to generate"
        )
        parser.add_argument(
            "--num_vehicles",
            type=int,
            default=20,
            help="Number of vehicles to generate",
        )
        parser.add_argument(
            "--num_carriers", type=int, default=5, help="Number of carriers to generate"
        )

    def handle(self, *args, **kwargs):
        self.num_trips = kwargs["num_trips"]
        self.num_branches = kwargs["num_branches"]
        self.num_drivers = kwargs["num_drivers"]
        self.num_vehicles = kwargs["num_vehicles"]
        self.num_carriers = kwargs["num_carriers"]

        self.stdout.write(self.style.SUCCESS("Generating carriers..."))
        carriers = self.create_carriers(self.num_carriers)

        self.stdout.write(self.style.SUCCESS("Generating branches..."))
        branches = self.create_branches(self.num_branches)

        self.stdout.write(self.style.SUCCESS("Generating vehicles..."))
        vehicles = self.create_vehicles(branches, carriers, self.num_vehicles)
        # vehicles = self.create_vehicles(carriers, self.num_vehicles)

        self.stdout.write(self.style.SUCCESS("Generating drivers..."))
        drivers = self.create_drivers(branches, self.num_drivers)

        self.stdout.write(self.style.SUCCESS("Generating locations..."))
        locations = self.create_locations(self.num_trips * 5)

        self.stdout.write(self.style.SUCCESS("Generating trips..."))
        trips = self.create_trips(drivers, vehicles, self.num_trips)

        self.stdout.write(self.style.SUCCESS("Generating trip events..."))
        self.create_trip_events(trips, locations)

        self.stdout.write(self.style.SUCCESS("Full seed generation complete!"))

    # --- Seed helpers ---
    def create_carriers(self, num=5):
        carriers = []
        for _ in range(num):
            carrier = Carrier(
                name=fake.company(),
                dot_number=str(randint(10000, 99999)),
                mc_number=str(randint(10000, 99999)),
                address=fake.address(),
                phone=fake.phone_number(),
            )
            carriers.append(carrier)
        Carrier.objects.bulk_create(carriers, ignore_conflicts=True)
        return list(Carrier.objects.all())

    def create_branches(self, num=5):
        branches = []
        cities = [
            "Kampala",
            "Mbarara",
            "Gulu",
            "Jinja",
            "Entebbe",
            "Mbale",
            "Lira",
            "Fort Portal",
        ]
        for _ in range(num):
            city = choice(cities)
            branch = Branch(
                name=f"{city} Branch",
                code=f"{city[:3].upper()}{randint(1,99)}",
                address=fake.address(),
                city=city,
                region=fake.state(),
                country="Uganda",
                phone_number=fake.phone_number(),
                email=fake.email(),
                latitude=round(uniform(-1.0, 3.0), 6),
                longitude=round(uniform(30.0, 35.0), 6),
                capacity=randint(5, 20),
            )
            branches.append(branch)
        Branch.objects.bulk_create(branches, ignore_conflicts=True)
        return list(Branch.objects.all())

    def create_vehicles(self, branches, carriers, num_vehicles):
        vehicles = []
        for _ in range(num_vehicles):
            vehicle = Vehicle.objects.create(
                truck_number=f"TRK-{randint(1000, 9999)}",
                make=fake.company(),
                model=fake.word(),
                year=randint(2000, 2025),
                vin=fake.unique.vin(),
                license_plate=fake.license_plate(),
                is_active=choice([True, False]),
                carrier=choice(carriers),
                branch=choice(branches),
            )
            vehicles.append(vehicle)
        return vehicles

    def create_drivers(self, branches, num=20):
        fake = Faker()
        # Ensure the branches list is not empty
        if not branches:
            raise ValueError("No branches available to assign drivers to.")

        drivers = []
        for _ in range(num):
            user = User.objects.create_user(
                username=fake.user_name(),
                email=fake.email(),
                role="driver",
                password="password123",
            )

            # Assign a random branch for the driver
            branch = choice(branches)

            # Create the driver with the branch assigned
            driver = Driver.objects.create(
                user=user,
                driver_initial=fake.unique.lexify(text="??") + str(randint(10, 99)),
                full_name=fake.name(),
                license_number=fake.unique.bothify(text="L########"),
                phone_number=fake.phone_number(),
                email=user.email,
                branch=branch,  # Make sure to assign the branch here
            )

            # Create BranchAssignment
            BranchAssignment.objects.create(
                user=user,
                branch=branch,
                start_date=timezone.now().date(),
                assignment_type="permanent",
                is_active=True,
            )

            # Append the driver to the list
            drivers.append(driver)

        return drivers

    def create_locations(self, num=100):
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
        trips = []
        statuses = ["active", "assigned", "ongoing", "completed"]
        for _ in range(num):
            driver = choice(drivers)
            co_driver = choice(drivers) if randint(0, 3) == 0 else None
            vehicle = choice(vehicles)
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
                duration = round(uniform(0.25, 4.0), 2)
                miles_driven = (
                    round(uniform(0, 250), 2) if event_type == "driving" else 0.0
                )
                events.append(
                    TripEvent(
                        trip=trip,
                        location=location,
                        event_type=event_type,
                        timestamp=timestamp,
                        duration=duration,
                        miles_driven=miles_driven,
                        notes=fake.text(max_nb_chars=100) if randint(0, 3) == 0 else "",
                    )
                )
                timestamp += timedelta(hours=duration)
        TripEvent.objects.bulk_create(events)
        self.stdout.write(self.style.SUCCESS(f"Created {len(events)} trip events"))
