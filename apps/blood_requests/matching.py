"""
Donor matching for a blood request.

Pure Python service so it can be called from views now and from an API or a
background job later without changes.
"""

from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.blood import match_priority
from apps.core.geo import haversine_km
from apps.donors.models import DonorProfile

from .models import BloodRequest, DonorResponse


@dataclass(frozen=True)
class Match:
    donor: DonorProfile
    distance_km: float | None
    priority: int


def find_matching_donors(blood_request: BloodRequest, radius_km: float | None = None, limit: int = 50) -> list[Match]:
    """
    Eligible, compatible donors near the request, best first:
    exact blood group, then other compatible groups, O- last; nearest first.

    If the request has no coordinates we fall back to donors in the same city.
    """
    radius_km = radius_km or settings.DEFAULT_MATCH_RADIUS_KM
    qs = (
        DonorProfile.objects.eligible()
        .compatible_with(blood_request.blood_group)
        .exclude(user_id=blood_request.requested_by_id)
        .exclude(responses__blood_request=blood_request)
        .select_related("user", "area")
    )

    location = blood_request.location
    matches: list[Match] = []
    if location:
        lat, lng = location
        for donor in qs.within_box(lat, lng, radius_km):
            distance = haversine_km(lat, lng, donor.latitude, donor.longitude)
            if distance <= radius_km:
                matches.append(
                    Match(donor, round(distance, 2), match_priority(donor.blood_group, blood_request.blood_group))
                )
    else:
        for donor in qs.filter(city_id=blood_request.city_id):
            matches.append(Match(donor, None, match_priority(donor.blood_group, blood_request.blood_group)))

    matches.sort(key=lambda m: (m.priority, m.distance_km if m.distance_km is not None else float("inf")))
    return matches[:limit]


@transaction.atomic
def create_notifications(blood_request: BloodRequest, matches: list[Match]) -> list[DonorResponse]:
    """Record which donors we are about to alert. Sending the actual push /
    email / WhatsApp message is Phase 3."""
    if blood_request.status != BloodRequest.Status.OPEN:
        raise ValueError("Only open requests can notify donors.")
    now = timezone.now()
    responses = [
        DonorResponse(blood_request=blood_request, donor=m.donor, distance_km=m.distance_km, notified_at=now)
        for m in matches
    ]
    return DonorResponse.objects.bulk_create(responses, ignore_conflicts=True)
