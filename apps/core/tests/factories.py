"""Tiny test helpers (no extra dependency)."""

import itertools
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import User
from apps.blood_requests.models import BloodRequest
from apps.core.models import City, Hospital
from apps.donors.models import DonorProfile

_seq = itertools.count(1000000)


def make_city(name="Wah Cantt", lat="33.783300", lng="72.716700"):
    city, _ = City.objects.get_or_create(name=name, defaults={"latitude": Decimal(lat), "longitude": Decimal(lng)})
    return city


def make_user(**kw):
    kw.setdefault("full_name", "Test User")
    return User.objects.create_user(phone=f"+92301{next(_seq)}", **kw)


def make_donor(blood_group="B+", city=None, lat=None, lng=None, **kw):
    city = city or make_city()
    now = timezone.now()
    defaults = dict(
        birth_year=timezone.localdate().year - 30,
        eligibility_confirmed_at=now,
        consent_given_at=now,
    )
    defaults.update(kw)
    return DonorProfile.objects.create(
        user=kw.pop("user", None) or make_user(),
        blood_group=blood_group,
        city=city,
        latitude=Decimal(lat) if lat else None,
        longitude=Decimal(lng) if lng else None,
        **{k: v for k, v in defaults.items() if k != "user"},
    )


def make_hospital(city=None, **kw):
    city = city or make_city()
    kw.setdefault("latitude", city.latitude)
    kw.setdefault("longitude", city.longitude)
    return Hospital.objects.create(name=kw.pop("name", "Test Hospital"), city=city, **kw)


def make_request(blood_group="B+", hospital=None, **kw):
    hospital = hospital or make_hospital()
    kw.setdefault("requested_by", make_user(full_name="Requester"))
    kw.setdefault("needed_by", timezone.now() + timedelta(hours=12))
    return BloodRequest.objects.create(
        patient_label="A.K.",
        blood_group=blood_group,
        hospital=hospital,
        city=hospital.city,
        attendant_phone="+923001234567",
        **kw,
    )
