from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.blood import BloodGroup, compatible_donor_groups
from apps.core.geo import bounding_box
from apps.core.models import LAT_VALIDATORS, LNG_VALIDATORS, Area, City, Hospital, TimeStampedModel


def _today() -> date:
    return timezone.localdate()


class DonorQuerySet(models.QuerySet):
    def active(self):
        return self.filter(user__is_active=True, consent_given_at__isnull=False)

    def available(self, today: date | None = None):
        today = today or _today()
        return self.active().filter(is_available=True).filter(Q(paused_until__isnull=True) | Q(paused_until__lt=today))

    def eligible(self, today: date | None = None):
        """Available donors who are past the donation interval, in the age
        range and have a recent eligibility self-check."""
        today = today or _today()
        interval = timedelta(days=settings.DONATION_INTERVAL_DAYS)
        confirm_cutoff = timezone.now() - timedelta(days=settings.ELIGIBILITY_CONFIRMATION_VALID_DAYS)
        return (
            self.available(today)
            .filter(Q(last_donation_date__isnull=True) | Q(last_donation_date__lte=today - interval))
            .filter(
                birth_year__lte=today.year - settings.DONOR_MIN_AGE,
                birth_year__gte=today.year - settings.DONOR_MAX_AGE,
            )
            .filter(eligibility_confirmed_at__gte=confirm_cutoff)
        )

    def compatible_with(self, recipient_group: str):
        return self.filter(blood_group__in=compatible_donor_groups(recipient_group))

    def within_box(self, lat, lng, radius_km: float):
        box = bounding_box(lat, lng, radius_km)
        return self.filter(
            latitude__gte=box.min_lat,
            latitude__lte=box.max_lat,
            longitude__gte=box.min_lng,
            longitude__lte=box.max_lng,
        )


class DonorProfile(TimeStampedModel):
    """
    What we deliberately do NOT store: disease history, HIV/hepatitis status,
    medications, exact address or full date of birth. Donors complete an
    eligibility self-check whose answers are never saved; we only record that
    and when they confirmed it. The blood bank does the real screening.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="donor_profile")
    blood_group = models.CharField(_("blood group"), max_length=3, choices=BloodGroup.choices)
    blood_group_verified = models.BooleanField(
        default=False, help_text=_("Confirmed by a recorded, verified donation.")
    )
    # Birth year is enough to check the age range.
    birth_year = models.PositiveSmallIntegerField(
        _("birth year"), validators=[MinValueValidator(1900), MaxValueValidator(2100)]
    )

    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="donors")
    area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True, blank=True, related_name="donors")
    # Approximate location (e.g. area centre), never a house address.
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=LAT_VALIDATORS)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=LNG_VALIDATORS)

    is_available = models.BooleanField(_("available to donate"), default=True)
    paused_until = models.DateField(
        _("paused until"),
        null=True,
        blank=True,
        help_text=_("Temporarily unavailable (illness, travel, etc.) until this date."),
    )
    # Kept in sync from Donation records, but donors can also enter it on sign-up.
    last_donation_date = models.DateField(_("last donation date"), null=True, blank=True)

    eligibility_confirmed_at = models.DateTimeField(null=True, blank=True)
    consent_given_at = models.DateTimeField(null=True, blank=True)
    privacy_policy_version = models.CharField(max_length=20, blank=True)

    notify_push = models.BooleanField(default=True)
    notify_email = models.BooleanField(default=False)
    notify_whatsapp = models.BooleanField(default=False)

    objects = DonorQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["blood_group", "is_available"]),
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["city", "blood_group"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(Q(latitude__isnull=True) & Q(longitude__isnull=True))
                | (Q(latitude__isnull=False) & Q(longitude__isnull=False)),
                name="donor_lat_lng_both_or_neither",
            ),
        ]

    def __str__(self):
        return f"{self.user} ({self.blood_group})"

    # --- validation -------------------------------------------------------

    def clean(self):
        today = _today()
        if self.last_donation_date and self.last_donation_date > today:
            raise ValidationError({"last_donation_date": _("Last donation date cannot be in the future.")})
        if self.area_id and self.city_id and self.area.city_id != self.city_id:
            raise ValidationError({"area": _("This area is not in the selected city.")})
        if self.birth_year and not (today.year - 100 <= self.birth_year <= today.year - settings.DONOR_MIN_AGE):
            raise ValidationError(
                {"birth_year": _("Donors must be at least %(age)s years old.") % {"age": settings.DONOR_MIN_AGE}}
            )

    def save(self, *args, **kwargs):
        # Fall back to the area's or city's centre so the donor can be matched by distance.
        if self.latitude is None or self.longitude is None:
            source = self.area if (self.area_id and self.area.has_location) else self.city
            if source is not None and source.has_location:
                self.latitude, self.longitude = source.latitude, source.longitude
        super().save(*args, **kwargs)

    # --- eligibility ------------------------------------------------------

    @property
    def approx_age(self) -> int:
        return _today().year - self.birth_year

    @property
    def next_eligible_date(self) -> date | None:
        if not self.last_donation_date:
            return None
        return self.last_donation_date + timedelta(days=settings.DONATION_INTERVAL_DAYS)

    def eligibility_confirmation_is_current(self) -> bool:
        if not self.eligibility_confirmed_at:
            return False
        valid_for = timedelta(days=settings.ELIGIBILITY_CONFIRMATION_VALID_DAYS)
        return timezone.now() - self.eligibility_confirmed_at <= valid_for

    def ineligibility_reasons(self, today: date | None = None) -> list[str]:
        """Empty list means the donor can be asked to donate today."""
        today = today or _today()
        reasons = []
        if not self.consent_given_at:
            reasons.append(_("Has not agreed to the privacy policy."))
        if not self.is_available:
            reasons.append(_("Marked as not available."))
        if self.paused_until and self.paused_until >= today:
            reasons.append(_("Paused until %(d)s.") % {"d": self.paused_until})
        if self.next_eligible_date and self.next_eligible_date > today:
            reasons.append(_("Can donate again from %(d)s.") % {"d": self.next_eligible_date})
        age = today.year - self.birth_year
        if age < settings.DONOR_MIN_AGE or age > settings.DONOR_MAX_AGE:
            reasons.append(_("Outside the donor age range."))
        if not self.eligibility_confirmation_is_current():
            reasons.append(_("Eligibility self-check needs to be completed."))
        return reasons

    def is_eligible(self, today: date | None = None) -> bool:
        return not self.ineligibility_reasons(today)

    def confirm_eligibility(self):
        self.eligibility_confirmed_at = timezone.now()
        self.save(update_fields=["eligibility_confirmed_at", "updated_at"])

    def give_consent(self):
        self.consent_given_at = timezone.now()
        self.privacy_policy_version = settings.PRIVACY_POLICY_VERSION
        self.save(update_fields=["consent_given_at", "privacy_policy_version", "updated_at"])

    def refresh_last_donation(self):
        latest = self.donations.order_by("-donated_on").values_list("donated_on", flat=True).first()
        self.last_donation_date = latest
        self.save(update_fields=["last_donation_date", "updated_at"])


class Donation(TimeStampedModel):
    donor = models.ForeignKey(DonorProfile, on_delete=models.CASCADE, related_name="donations")
    donated_on = models.DateField(_("donated on"))
    hospital = models.ForeignKey(Hospital, on_delete=models.SET_NULL, null=True, blank=True, related_name="donations")
    blood_request = models.ForeignKey(
        "blood_requests.BloodRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="donations"
    )
    units = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(2)])
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-donated_on"]
        constraints = [
            models.UniqueConstraint(fields=["donor", "donated_on"], name="one_donation_per_donor_per_day"),
        ]

    def __str__(self):
        return f"{self.donor} on {self.donated_on}"

    def clean(self):
        if self.donated_on and self.donated_on > _today():
            raise ValidationError({"donated_on": _("Donation date cannot be in the future.")})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.donor.refresh_last_donation()

    def delete(self, *args, **kwargs):
        donor = self.donor
        result = super().delete(*args, **kwargs)
        donor.refresh_last_donation()
        return result

    def verify(self, moderator):
        self.verified_by = moderator
        self.verified_at = timezone.now()
        self.save(update_fields=["verified_by", "verified_at", "updated_at"])
        if not self.donor.blood_group_verified:
            self.donor.blood_group_verified = True
            self.donor.save(update_fields=["blood_group_verified", "updated_at"])
