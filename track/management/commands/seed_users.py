from django.core.management.base import BaseCommand
from faker import Faker
import random
from datetime import timedelta, date
from django.utils import timezone

from user.models import (
    User,
    Branch,
    BranchManager,
    BranchAssignment,
    Driver,
    Carrier,
)
from track.models import Vehicle


class Command(BaseCommand):
    help = "Seed admin dashboard with branches, users, and vehicles"

    def add_arguments(self, parser):
        # Adding arguments to control the amount of data
        parser.add_argument(
            "--branches",
            type=int,
            default=10,
            help="Number of branches to create (default: 4)",
        )
        parser.add_argument(
            "--drivers",
            type=int,
            default=30,
            help="Number of drivers to create per branch (default: 5)",
        )
        parser.add_argument(
            "--vehicles",
            type=int,
            default=30,
            help="Number of vehicles to create per branch (default: 30)",
        )

    def handle(self, *args, **kwargs):
        fake = Faker()

        # Get the number of entities to create from the command-line arguments
        num_branches = kwargs["branches"]
        num_drivers_per_branch = kwargs["drivers"]
        num_vehicles_per_branch = kwargs["vehicles"]

        # Create a carrier first (for vehicles)
        carrier, _ = Carrier.objects.get_or_create(
            name="Uganda Fleet Services",
            defaults={
                "dot_number": f"DOT{random.randint(1000, 9999)}",
                "mc_number": f"MC{random.randint(1000, 9999)}",
                "phone": "+256700000000",
            },
        )

        # Create branches (adjusting based on the input)
        branches_data = [
            {
                "name": "Kampala Central Depot",
                "code": "KLA",
                "city": "Kampala",
                "region": "Central",
                "address": "Plot 123, Kampala Road",
                "phone_number": "+256700123456",
                "email": "kampala@fleet.ug",
                "latitude": 0.3476,
                "longitude": 32.5825,
                "capacity": 50,
            },
            {
                "name": "Mbarara Regional Hub",
                "code": "MBS",
                "city": "Mbarara",
                "region": "Western",
                "address": "Plot 456, Mbarara-Masaka Road",
                "phone_number": "+256700234567",
                "email": "mbarara@fleet.ug",
                "latitude": -0.6003,
                "longitude": 30.6583,
                "capacity": 40,
            },
            {
                "name": "Gulu Northern Depot",
                "code": "GUL",
                "city": "Gulu",
                "region": "Northern",
                "address": "Plot 789, Gulu Main Street",
                "phone_number": "+256700345678",
                "email": "gulu@fleet.ug",
                "latitude": 2.7747,
                "longitude": 32.2989,
                "capacity": 35,
            },
            {
                "name": "Jinja Eastern Branch",
                "code": "JIN",
                "city": "Jinja",
                "region": "Eastern",
                "address": "Plot 321, Jinja-Kampala Highway",
                "phone_number": "+256700456789",
                "email": "jinja@fleet.ug",
                "latitude": 0.4244,
                "longitude": 33.2040,
                "capacity": 30,
            },
        ]

        # Limit the number of branches to the user-specified number
        branches_data = branches_data[:num_branches]

        branches = []
        for branch_data in branches_data:
            branch, created = Branch.objects.get_or_create(
                code=branch_data["code"], defaults=branch_data
            )
            branches.append(branch)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created branch: {branch.name}"))

        # Create admin user
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@fleet.ug",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin_user.set_password("admin123")
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created admin user"))

        # Create branch managers
        for i, branch in enumerate(branches):
            # Create branch manager user
            manager_user, created = User.objects.get_or_create(
                username=f"manager_{branch.code.lower()}",
                defaults={
                    "email": f"manager.{branch.code.lower()}@fleet.ug",
                    "role": "branch-manager",
                    "primary_branch": branch,
                },
            )
            if created:
                manager_user.set_password("manager123")
                manager_user.save()
                self.stdout.write(
                    self.style.SUCCESS(f"Created manager for {branch.name}")
                )

            # Create BranchManager relationship
            BranchManager.objects.get_or_create(
                user=manager_user,
                branch=branch,
                defaults={
                    "role": "manager",
                    "is_primary": True,
                    "can_approve_trips": True,
                    "can_assign_drivers": True,
                    "can_manage_vehicles": True,
                    "can_approve_maintenance": True,
                    "can_view_reports": True,
                },
            )

        # Create drivers for each branch
        driver_users = []
        drivers = []
        for branch in branches:
            for i in range(num_drivers_per_branch):
                driver_initial = f"{branch.code}{random.randint(10, 99)}"

                # Create driver user
                driver_user, created = User.objects.get_or_create(
                    username=f"driver_{driver_initial.lower()}",
                    defaults={
                        "email": f"driver.{driver_initial.lower()}@fleet.ug",
                        "role": "driver",
                        "primary_branch": branch,
                    },
                )
                if created:
                    driver_user.set_password("driver123")
                    driver_user.save()
                    driver_users.append(driver_user)

                    # Create Driver profile
                    driver = Driver.objects.create(
                        user=driver_user,
                        driver_initial=driver_initial,
                        full_name=fake.name(),
                        license_number=f"DL{random.randint(100000, 999999)}",
                        phone_number=f"+25670{random.randint(1000000, 9999999)}",
                        email=driver_user.email,
                    )
                    drivers.append(driver)

                    # Create branch assignment
                    BranchAssignment.objects.create(
                        user=driver_user,
                        branch=branch,
                        assignment_type="permanent",
                        start_date=date.today()
                        - timedelta(days=random.randint(30, 365)),
                        is_active=True,
                    )

        self.stdout.write(self.style.SUCCESS(f"Created {len(drivers)} drivers"))

        # Create vehicles for each branch
        vehicle_count = 0
        for branch in branches:
            for i in range(num_vehicles_per_branch):
                truck_number = f'UB{random.choice(["A", "B", "D", "Z"])}{random.randint(100, 999)}{random.choice(["A", "B", "H", "Z"])}'

                try:
                    vehicle = Vehicle.objects.create(
                        truck_number=truck_number,
                        make=random.choice(["Isuzu", "Fuso", "Mercedes", "Volvo"]),
                        model=random.choice(["FVR", "Fighter", "Actros", "FM"]),
                        year=random.randint(2015, 2024),
                        vin=f"VIN{random.randint(10000000000000, 99999999999999)}",
                        license_plate=f"UB{random.randint(1000, 9999)}",
                        carrier=carrier,
                        status="active",
                        current_branch=branch,
                    )
                    vehicle_count += 1
                except Exception as e:
                    continue

        self.stdout.write(self.style.SUCCESS(f"Created {vehicle_count} vehicles"))
        self.stdout.write(self.style.SUCCESS("Dashboard data seeded successfully!"))


# # management/commands/seed_admin_dashboard.py

# from django.core.management.base import BaseCommand
# from faker import Faker
# import random
# from datetime import timedelta, date
# from django.utils import timezone

# from user.models import (
#     User,
#     Branch,
#     BranchManager,
#     BranchAssignment,
#     Driver,
#     Carrier,
# )
# from track.models import Vehicle


# class Command(BaseCommand):
#     help = "Seed admin dashboard with branches, users, and vehicles"

#     def handle(self, *args, **kwargs):
#         fake = Faker()

#         # Create a carrier first (for vehicles)
#         carrier, _ = Carrier.objects.get_or_create(
#             name="Uganda Fleet Services",
#             defaults={
#                 "dot_number": f"DOT{random.randint(1000, 9999)}",
#                 "mc_number": f"MC{random.randint(1000, 9999)}",
#                 "phone": "+256700000000",
#             },
#         )

#         # Create branches
#         branches_data = [
#             {
#                 "name": "Kampala Central Depot",
#                 "code": "KLA",
#                 "city": "Kampala",
#                 "region": "Central",
#                 "address": "Plot 123, Kampala Road",
#                 "phone_number": "+256700123456",
#                 "email": "kampala@fleet.ug",
#                 "latitude": 0.3476,
#                 "longitude": 32.5825,
#                 "capacity": 50,
#             },
#             {
#                 "name": "Mbarara Regional Hub",
#                 "code": "MBS",
#                 "city": "Mbarara",
#                 "region": "Western",
#                 "address": "Plot 456, Mbarara-Masaka Road",
#                 "phone_number": "+256700234567",
#                 "email": "mbarara@fleet.ug",
#                 "latitude": -0.6003,
#                 "longitude": 30.6583,
#                 "capacity": 40,
#             },
#             {
#                 "name": "Gulu Northern Depot",
#                 "code": "GUL",
#                 "city": "Gulu",
#                 "region": "Northern",
#                 "address": "Plot 789, Gulu Main Street",
#                 "phone_number": "+256700345678",
#                 "email": "gulu@fleet.ug",
#                 "latitude": 2.7747,
#                 "longitude": 32.2989,
#                 "capacity": 35,
#             },
#             {
#                 "name": "Jinja Eastern Branch",
#                 "code": "JIN",
#                 "city": "Jinja",
#                 "region": "Eastern",
#                 "address": "Plot 321, Jinja-Kampala Highway",
#                 "phone_number": "+256700456789",
#                 "email": "jinja@fleet.ug",
#                 "latitude": 0.4244,
#                 "longitude": 33.2040,
#                 "capacity": 30,
#             },
#         ]

#         branches = []
#         for branch_data in branches_data:
#             branch, created = Branch.objects.get_or_create(
#                 code=branch_data["code"], defaults=branch_data
#             )
#             branches.append(branch)
#             if created:
#                 self.stdout.write(self.style.SUCCESS(f"Created branch: {branch.name}"))

#         # Create admin user
#         admin_user, created = User.objects.get_or_create(
#             username="admin",
#             defaults={
#                 "email": "admin@fleet.ug",
#                 "role": "admin",
#                 "is_staff": True,
#                 "is_superuser": True,
#             },
#         )
#         if created:
#             admin_user.set_password("admin123")
#             admin_user.save()
#             self.stdout.write(self.style.SUCCESS("Created admin user"))

#         # Create branch managers
#         for i, branch in enumerate(branches):
#             # Create branch manager user
#             manager_user, created = User.objects.get_or_create(
#                 username=f"manager_{branch.code.lower()}",
#                 defaults={
#                     "email": f"manager.{branch.code.lower()}@fleet.ug",
#                     "role": "branch-manager",
#                     "primary_branch": branch,
#                 },
#             )
#             if created:
#                 manager_user.set_password("manager123")
#                 manager_user.save()
#                 self.stdout.write(
#                     self.style.SUCCESS(f"Created manager for {branch.name}")
#                 )

#             # Create BranchManager relationship
#             BranchManager.objects.get_or_create(
#                 user=manager_user,
#                 branch=branch,
#                 defaults={
#                     "role": "manager",
#                     "is_primary": True,
#                     "can_approve_trips": True,
#                     "can_assign_drivers": True,
#                     "can_manage_vehicles": True,
#                     "can_approve_maintenance": True,
#                     "can_view_reports": True,
#                 },
#             )

#             # Create fleet manager user (supervises 2 branches)
#             if i < 2:
#                 fleet_manager, created = User.objects.get_or_create(
#                     username=f"fleet_manager_{i+1}",
#                     defaults={
#                         "email": f"fleet.manager{i+1}@fleet.ug",
#                         "role": "fleet-manager",
#                         "primary_branch": branch,
#                     },
#                 )
#                 if created:
#                     fleet_manager.set_password("fleet123")
#                     fleet_manager.save()

#                 BranchManager.objects.get_or_create(
#                     user=fleet_manager,
#                     branch=branch,
#                     defaults={
#                         "role": "supervisor",
#                         "is_primary": True if i == 0 else False,
#                     },
#                 )

#         # Create drivers for each branch
#         driver_users = []
#         drivers = []
#         for branch in branches:
#             num_drivers = random.randint(5, 10)

#             for i in range(num_drivers):
#                 driver_initial = f"{branch.code}{random.randint(10, 99)}"

#                 # Create driver user
#                 driver_user, created = User.objects.get_or_create(
#                     username=f"driver_{driver_initial.lower()}",
#                     defaults={
#                         "email": f"driver.{driver_initial.lower()}@fleet.ug",
#                         "role": "driver",
#                         "primary_branch": branch,
#                     },
#                 )
#                 if created:
#                     driver_user.set_password("driver123")
#                     driver_user.save()
#                     driver_users.append(driver_user)

#                     # Create Driver profile
#                     driver = Driver.objects.create(
#                         user=driver_user,
#                         driver_initial=driver_initial,
#                         full_name=fake.name(),
#                         license_number=f"DL{random.randint(100000, 999999)}",
#                         phone_number=f"+25670{random.randint(1000000, 9999999)}",
#                         email=driver_user.email,
#                     )
#                     drivers.append(driver)

#                     # Create branch assignment
#                     BranchAssignment.objects.create(
#                         user=driver_user,
#                         branch=branch,
#                         assignment_type="permanent",
#                         start_date=date.today()
#                         - timedelta(days=random.randint(30, 365)),
#                         is_active=True,
#                     )

#         self.stdout.write(self.style.SUCCESS(f"Created {len(drivers)} drivers"))

#         # Create vehicles for each branch
#         vehicle_count = 0
#         for branch in branches:
#             num_vehicles = random.randint(30, 50)

#             for i in range(num_vehicles):
#                 truck_number = f'UB{random.choice(["A", "B", "D", "Z"])}{random.randint(100, 999)}{random.choice(["A", "B", "H", "Z"])}'

#                 try:
#                     vehicle = Vehicle.objects.create(
#                         truck_number=truck_number,
#                         make=random.choice(["Isuzu", "Fuso", "Mercedes", "Volvo"]),
#                         model=random.choice(["FVR", "Fighter", "Actros", "FM"]),
#                         year=random.randint(2015, 2024),
#                         vin=f"VIN{random.randint(10000000000000, 99999999999999)}",
#                         license_plate=f"UB{random.randint(1000, 9999)}",
#                         carrier=carrier,
#                         status="active",
#                         current_branch=branch,
#                     )
#                     vehicle_count += 1
#                 except Exception as e:
#                     continue

#         self.stdout.write(self.style.SUCCESS(f"Created {vehicle_count} vehicles"))
#         self.stdout.write(self.style.SUCCESS("Dashboard data seeded successfully!"))
