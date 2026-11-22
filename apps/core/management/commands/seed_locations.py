from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.core.models import City

# Approximate city centres. Areas and hospitals are added from the admin so
# names and locations come from people who know the town.
CITIES = [
    ("Wah Cantt", "واہ کینٹ", Decimal("33.783300"), Decimal("72.716700")),
    ("Taxila", "ٹیکسلا", Decimal("33.745800"), Decimal("72.787500")),
]


class Command(BaseCommand):
    help = "Create the launch cities (safe to run more than once)."

    def handle(self, *args, **options):
        for name, name_ur, lat, lng in CITIES:
            city, created = City.objects.update_or_create(
                name=name, defaults={"name_ur": name_ur, "latitude": lat, "longitude": lng}
            )
            self.stdout.write(f"{'Created' if created else 'Updated'} {city}")
