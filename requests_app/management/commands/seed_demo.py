"""
Demo accounts for local use and the deployed demo. All share DEMO_PASSWORD.
These numbers are in the 0700 000 0xx range and are not real subscribers.
"""

import os

from django.core.management.base import BaseCommand

from accounts.models import Role, User
from requests_app.models import Department

DEMO_ACCOUNTS = [
    ("+254700000001", "Wanjiru Kamau (demo citizen)", Role.CITIZEN, None),
    ("+254700000002", "Otieno Mwangi (demo citizen)", Role.CITIZEN, None),
    ("+254700000010", "Water officer (demo)", Role.OFFICER, "water"),
    ("+254700000011", "Roads officer (demo)", Role.OFFICER, "roads"),
    ("+254700000012", "Environment officer (demo)", Role.OFFICER, "environment"),
    ("+254700000099", "County administrator (demo)", Role.ADMIN, None),
]

REPLAY_ACCOUNT = "system:nyc311-replay"


class Command(BaseCommand):
    help = "Create (or reset the passwords of) the demo accounts."

    def handle(self, *args, **options):
        password = os.environ.get("DEMO_PASSWORD")
        if not password:
            password = "Murang-a-demo-2026"
            self.stdout.write(self.style.WARNING("DEMO_PASSWORD not set; using the default from .env.example."))
        for phone, name, role, dept_code in DEMO_ACCOUNTS:
            department = Department.objects.get(code=dept_code) if dept_code else None
            user, _ = User.objects.update_or_create(
                phone=phone,
                defaults={"full_name": name, "role": role, "department": department,
                          "is_staff": role == Role.ADMIN, "is_superuser": role == Role.ADMIN},
            )
            user.set_password(password)
            user.save()
        replay, _ = User.objects.get_or_create(
            phone=REPLAY_ACCOUNT, defaults={"full_name": "NYC 311 replay (dataset)", "is_active": False}
        )
        replay.set_unusable_password()
        replay.save()
        self.stdout.write(self.style.SUCCESS(f"{len(DEMO_ACCOUNTS)} demo accounts ready."))
