from django.core.management.base import BaseCommand

from apps.blood_requests.models import BloodRequest


class Command(BaseCommand):
    help = "Expire requests whose 'needed by' time has passed. Run on a schedule (e.g. hourly)."

    def handle(self, *args, **options):
        count = 0
        for br in BloodRequest.objects.overdue():
            br.expire()
            count += 1
        self.stdout.write(f"Expired {count} request(s).")
