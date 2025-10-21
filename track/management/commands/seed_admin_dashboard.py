# management/commands/seed_admin_dashboard.py

from django.core.management.base import BaseCommand
from faker import Faker
import random
from datetime import timedelta
from django.utils import timezone

from backend.track.models import Carrier, Vehicle


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        fake = Faker()

        # Create carriers/branches
        branches = [
            "Kampala Central Depot",
            "Mbarara Regional Hub",
            "Gulu Northern Depot",
            "Jinja Eastern Branch",
        ]

        for branch_name in branches:
            carrier, created = Carrier.objects.get_or_create(
                name=branch_name,
                defaults={
                    "dot_number": f"DOT{random.randint(1000, 9999)}",
                    "phone": fake.phone_number(),
                },
            )

            # Create vehicles for each branch
            for i in range(random.randint(30, 50)):
                vehicle = Vehicle.objects.create(
                    truck_number=f'UB{random.choice(["A", "B", "D", "Z"])}{random.randint(100, 999)}{random.choice(["A", "B", "H", "Z"])}',
                    make=random.choice(["Isuzu", "Fuso", "Mercedes", "Volvo"]),
                    model=random.choice(["FVR", "Fighter", "Actros", "FM"]),
                    year=random.randint(2015, 2024),
                    carrier=carrier,
                )

        self.stdout.write(self.style.SUCCESS("Dashboard data seeded successfully"))
