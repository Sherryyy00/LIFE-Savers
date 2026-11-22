"""
Fake data for local development ONLY. Refuses to run when DEBUG is off.
All names and numbers are made up.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import User
from apps.blood_requests.models import BloodRequest
from apps.core.blood import BloodGroup
from apps.core.models import Area, City, Hospital
from apps.donors.models import DonorProfile

FIRST = ["Ali", "Ahmed", "Usman", "Hamza", "Bilal", "Ayesha", "Fatima", "Zainab", "Sana", "Hira"]
LAST = ["Khan", "Malik", "Butt", "Qureshi", "Raja", "Awan", "Abbasi", "Shah"]


class Command(BaseCommand):
    help = "Load fake demo donors, areas, hospitals and requests (DEBUG only)."

    def add_arguments(self, parser):
        parser.add_argument("--donors", type=int, default=60)

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DEBUG=True.")
        random.seed(42)
        call_command("seed_locations")
        wah = City.objects.get(name="Wah Cantt")
        taxila = City.objects.get(name="Taxila")

        areas = []
        for i, city in enumerate([wah, wah, wah, taxila, taxila]):
            area, _ = Area.objects.get_or_create(
                city=city,
                name=f"Demo Area {i + 1}",
                defaults={
                    "latitude": city.latitude + Decimal(random.uniform(-0.02, 0.02)).quantize(Decimal("0.000001")),
                    "longitude": city.longitude + Decimal(random.uniform(-0.02, 0.02)).quantize(Decimal("0.000001")),
                },
            )
            areas.append(area)

        hospital, _ = Hospital.objects.get_or_create(
            name="Demo General Hospital",
            city=wah,
            defaults={
                "latitude": wah.latitude,
                "longitude": wah.longitude,
                "has_blood_bank": True,
                "is_verified": True,
            },
        )

        groups = [g for g, _ in BloodGroup.choices]
        weights = [27, 2, 30, 2, 7, 1, 29, 2]  # rough population spread, O+ and B+ most common
        now = timezone.now()
        created = 0
        for i in range(opts["donors"]):
            phone = f"+92300{1000000 + i}"
            if User.objects.filter(phone=phone).exists():
                continue
            user = User.objects.create_user(phone=phone, full_name=f"{random.choice(FIRST)} {random.choice(LAST)}")
            area = random.choice(areas)
            last = None if random.random() < 0.4 else timezone.localdate() - timedelta(days=random.randint(10, 400))
            DonorProfile.objects.create(
                user=user,
                blood_group=random.choices(groups, weights)[0],
                birth_year=random.randint(1968, 2006),
                city=area.city,
                area=area,
                last_donation_date=last,
                is_available=random.random() > 0.1,
                eligibility_confirmed_at=now,
                consent_given_at=now,
                privacy_policy_version=settings.PRIVACY_POLICY_VERSION,
            )
            created += 1

        requester, _ = User.objects.get_or_create(phone="+923009999999", defaults={"full_name": "Demo Requester"})
        if not BloodRequest.objects.exists():
            BloodRequest.objects.create(
                requested_by=requester,
                patient_label="A.K.",
                blood_group="B-",
                units_needed=2,
                hospital=hospital,
                city=wah,
                attendant_phone="+923001234567",
                needed_by=now + timedelta(hours=6),
                urgency=BloodRequest.Urgency.CRITICAL,
            )
        self.stdout.write(self.style.SUCCESS(f"Demo data ready: {created} new donors."))
