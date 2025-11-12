from django.core.management.base import BaseCommand
from faker import Faker
from random import randint, uniform, choice
from django.utils import timezone
from datetime import timedelta

from track.models import Location, Vehicle, Trip, TripEvent
from user.models import (
    Organization,
    Branch,
    BranchManager,
    BranchAssignment,
    Driver,
    Carrier,
    User,
)

fake = Faker()


class Command(BaseCommand):
    help = "Seed the database with demo data for organizations, branches, vehicles, drivers, and trips"

    def add_arguments(self, parser):
        parser.add_argument("--num_orgs", type=int, default=3)
        parser.add_argument("--num_carriers", type=int, default=5)
        parser.add_argument("--num_branches", type=int, default=8)
        parser.add_argument("--num_drivers", type=int, default=20)
        parser.add_argument("--num_vehicles", type=int, default=15)
        parser.add_argument("--num_trips", type=int, default=50)

    def handle(self, *args, **kwargs):
        num_orgs = kwargs["num_orgs"]
        num_carriers = kwargs["num_carriers"]
        num_branches = kwargs["num_branches"]
        num_drivers = kwargs["num_drivers"]
        num_vehicles = kwargs["num_vehicles"]
        num_trips = kwargs["num_trips"]

        self.stdout.write(self.style.SUCCESS("🚧 Starting data seeding..."))

        organizations = self.create_organizations(num_orgs)
        carriers = self.create_carriers(num_carriers)
        branches = self.create_branches(organizations, num_branches)
        self.create_branch_managers(branches)
        vehicles = self.create_vehicles(branches, carriers, num_vehicles)
        drivers = self.create_drivers(branches, num_drivers)
        locations = self.create_locations(num_trips * 5)
        trips = self.create_trips(drivers, vehicles, locations, num_trips)
        self.create_trip_events(trips, locations)

        self.stdout.write(
            self.style.SUCCESS("✅ Database seeding completed successfully!")
        )

    # ---------------------
    # ORGANIZATIONS
    # ---------------------
    def create_organizations(self, num):
        orgs = []
        for _ in range(num):
            orgs.append(
                Organization(
                    name=fake.company(),
                    code=f"ORG{randint(100,999)}",
                    registration_number=fake.ean(length=8),
                    email=fake.company_email(),
                    phone_number=fake.msisdn(),
                    address=fake.address(),
                    website=fake.url(),
                    industry=choice(["Transport", "Logistics", "Distribution"]),
                    description=fake.text(max_nb_chars=120),
                )
            )
        Organization.objects.bulk_create(orgs, ignore_conflicts=True)
        return list(Organization.objects.all())

    # ---------------------
    # CARRIERS
    # ---------------------
    def create_carriers(self, num):
        carriers = []
        for _ in range(num):
            carriers.append(
                Carrier(
                    name=fake.company(),
                    dot_number=str(randint(10000, 99999)),
                    mc_number=str(randint(10000, 99999)),
                    address=fake.address(),
                    phone=fake.phone_number(),
                )
            )
        Carrier.objects.bulk_create(carriers, ignore_conflicts=True)
        return list(Carrier.objects.all())

    # ---------------------
    # BRANCHES
    # ---------------------
    def create_branches(self, organizations, num):
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
            org = choice(organizations)
            city = choice(cities)
            branches.append(
                Branch(
                    organization=org,
                    name=f"{city} Branch - {org.code}",
                    code=f"{city[:3].upper()}{randint(1,99)}",
                    address=fake.address(),
                    city=city,
                    region=fake.state(),
                    country="Uganda",
                    phone_number=f"+256{randint(700000000,799999999)}",
                    email=fake.company_email(),
                    latitude=round(uniform(-1.0, 3.0), 6),
                    longitude=round(uniform(30.0, 35.0), 6),
                    capacity=randint(5, 20),
                    status=choice(["active", "inactive", "maintenance"]),
                )
            )
        Branch.objects.bulk_create(branches, ignore_conflicts=True)
        return list(Branch.objects.all())

    # ---------------------
    # BRANCH MANAGERS
    # ---------------------
    def create_branch_managers(self, branches):
        for branch in branches:
            user = User.objects.create_user(
                username=f"{branch.code.lower()}_manager",
                email=f"{branch.code.lower()}@{branch.organization.code.lower()}.com",
                role="branch-manager",
                password="password123",
            )
            BranchManager.objects.create(user=user, branch=branch, role="manager")

    # ---------------------
    # VEHICLES
    # ---------------------
    def create_vehicles(self, branches, carriers, num):
        vehicles = []
        for _ in range(num):
            vehicles.append(
                Vehicle(
                    truck_number=f"TRK-{randint(1000, 9999)}",
                    make=fake.company(),
                    model=fake.word(),
                    year=randint(2000, 2025),
                    vin=fake.unique.bothify(text="?????????????????"),
                    license_plate=fake.bothify(text="U?? ####"),
                    is_active=choice([True, False]),
                    carrier=choice(carriers),
                    branch=choice(branches),
                )
            )
        Vehicle.objects.bulk_create(vehicles, ignore_conflicts=True)
        return list(Vehicle.objects.all())

    # ---------------------
    # DRIVERS
    # ---------------------
    def create_drivers(self, branches, num):
        drivers = []
        for _ in range(num):
            user = User.objects.create_user(
                username=fake.user_name(),
                email=fake.email(),
                role="driver",
                password="password123",
            )
            branch = choice(branches)
            driver = Driver.objects.create(
                user=user,
                driver_initial=fake.unique.lexify(text="??") + str(randint(10, 99)),
                full_name=fake.name(),
                license_number=fake.unique.bothify(text="L########"),
                phone_number=f"+256{randint(700000000,799999999)}",
                email=user.email,
                branch=branch,
            )
            BranchAssignment.objects.create(
                user=user,
                branch=branch,
                start_date=timezone.now().date(),
                assignment_type="permanent",
                is_active=True,
            )
            drivers.append(driver)
        return drivers

    # ---------------------
    # LOCATIONS
    # ---------------------
    def create_locations(self, num):
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
            city, lat, lon = choice(ugandan_cities)
            locations.append(
                Location(
                    address=fake.street_address(),
                    latitude=round(lat + uniform(-0.05, 0.05), 6),
                    longitude=round(lon + uniform(-0.05, 0.05), 6),
                    city=city,
                    state=fake.state_abbr(),
                    country="Uganda",
                    postal_code=fake.postcode(),
                )
            )
        Location.objects.bulk_create(locations, ignore_conflicts=True)
        return list(Location.objects.all())

    # ---------------------
    # TRIPS
    # ---------------------
    def create_trips(self, drivers, vehicles, locations, num):
        trips = []
        statuses = ["active", "assigned", "ongoing", "completed"]
        for _ in range(num):
            driver = choice(drivers)
            co_driver = choice(drivers) if randint(0, 4) == 0 else None
            vehicle = choice(vehicles)
            origin = choice(locations)
            destination = choice([loc for loc in locations if loc != origin])

            trip_date = timezone.now().date() - timedelta(days=randint(0, 30))
            is_completed = choice([True, False])

            trip = Trip(
                date=trip_date,
                driver=driver,
                co_driver=co_driver,
                vehicle=vehicle,
                shipper_and_commodity=f"{fake.company()} - {fake.word()}",
                cycle_rule=choice(["70hr/8day", "60hr/7day"]),
                remarks=f"Trip from {origin.city} to {destination.city}",
                is_completed=is_completed,
                status="completed" if is_completed else choice(statuses),
            )
            trip._origin = origin
            trip._destination = destination  # temporary for event seeding
            trips.append(trip)

        Trip.objects.bulk_create(trips)
        return list(Trip.objects.order_by("-created_at")[:num])

    # ---------------------
    # TRIP EVENTS (with origin/destination)
    # ---------------------
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
            "other",
        ]

        for trip in trips:
            origin = getattr(trip, "_origin", choice(locations))
            destination = getattr(trip, "_destination", choice(locations))

            num_events = randint(6, 15)
            timestamp = timezone.make_aware(
                timezone.datetime.combine(trip.date, timezone.datetime.min.time())
            )

            # Origin event
            events.append(
                TripEvent(
                    trip=trip,
                    location=origin,
                    event_type="loading",
                    timestamp=timestamp,
                    duration=round(uniform(0.5, 2.0), 2),
                    miles_driven=0.0,
                    notes=f"Trip started at {origin.city}",
                )
            )
            timestamp += timedelta(hours=1)

            # Mid-route events
            for _ in range(num_events - 2):
                location = choice(locations)
                event_type = choice(event_types)
                duration = round(uniform(0.25, 4.0), 2)
                miles = round(uniform(10, 200), 2) if event_type == "driving" else 0.0
                events.append(
                    TripEvent(
                        trip=trip,
                        location=location,
                        event_type=event_type,
                        timestamp=timestamp,
                        duration=duration,
                        miles_driven=miles,
                        notes=fake.sentence(nb_words=8),
                    )
                )
                timestamp += timedelta(hours=duration)

            # Destination event
            events.append(
                TripEvent(
                    trip=trip,
                    location=destination,
                    event_type="unloading",
                    timestamp=timestamp,
                    duration=round(uniform(0.5, 2.0), 2),
                    miles_driven=0.0,
                    notes=f"Trip ended at {destination.city}",
                )
            )

        TripEvent.objects.bulk_create(events)
        self.stdout.write(
            self.style.SUCCESS(
                f"📍 Created {len(events)} TripEvents with origin/destination"
            )
        )
