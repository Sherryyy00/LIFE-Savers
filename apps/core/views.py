from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from apps.blood_requests.models import BloodRequest
from apps.donors.models import DonorProfile


def home(request):
    context = {
        "donor_count": DonorProfile.objects.active().count(),
        "open_requests": BloodRequest.objects.open().count(),
    }
    return render(request, "core/home.html", context)


def healthz(request):
    """Used by Render's health check and uptime pings."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})
