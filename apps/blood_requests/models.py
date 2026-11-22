import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from apps.core.blood import BloodGroup
from apps.core.models import City, Hospital, TimeStampedModel

# No 0/O/1/I so codes are easy to read out over the phone.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_reference() -> str:
    return "LS-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


class InvalidTransition(Exception):
    pass


class BloodRequestQuerySet(models.QuerySet):
    def open(self):
        return self.filter(status=BloodRequest.Status.OPEN)

    def needs_review(self):
        return self.filter(status=BloodRequest.Status.PENDING_REVIEW)

    def overdue(self, now=None):
        now = now or timezone.now()
        return self.filter(
            status__in=[BloodRequest.Status.PENDING_REVIEW, BloodRequest.Status.OPEN],
            needed_by__lt=now,
        )


class BloodRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING_REVIEW = "pending_review", _("Waiting for review")
        OPEN = "open", _("Open")
        FULFILLED = "fulfilled", _("Fulfilled")
        CANCELLED = "cancelled", _("Cancelled")
        EXPIRED = "expired", _("Expired")
        REJECTED = "rejected", _("Rejected")

    class Urgency(models.TextChoices):
        CRITICAL = "critical", _("Critical (within hours)")
        URGENT = "urgent", _("Urgent (within 24 hours)")
        PLANNED = "planned", _("Planned (surgery, thalassaemia transfusion)")

    ACTIVE_STATUSES = (Status.PENDING_REVIEW, Status.OPEN)

    reference = models.CharField(max_length=12, unique=True, default=generate_reference, editable=False)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="blood_requests")

    # Minimal patient info: a first name or initials helps the donor find the
    # right person at the hospital. No diagnosis is collected.
    patient_label = models.CharField(_("patient first name or initials"), max_length=50)
    blood_group = models.CharField(_("blood group needed"), max_length=3, choices=BloodGroup.choices)
    units_needed = models.PositiveSmallIntegerField(
        _("units needed"), default=1, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )

    hospital = models.ForeignKey(
        Hospital, on_delete=models.PROTECT, null=True, blank=True, related_name="blood_requests"
    )
    hospital_other = models.CharField(_("hospital (if not listed)"), max_length=150, blank=True)
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="blood_requests")
    ward_or_bed = models.CharField(_("ward / bed"), max_length=50, blank=True)

    # Only shown to donors who accept this request.
    attendant_phone = PhoneNumberField(_("attendant phone"))
    needed_by = models.DateTimeField(_("needed by"))
    urgency = models.CharField(max_length=10, choices=Urgency.choices, default=Urgency.URGENT)
    notes = models.TextField(_("notes"), max_length=500, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_REVIEW)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = BloodRequestQuerySet.as_manager()

    class Meta:
        ordering = ["needed_by"]
        indexes = [
            models.Index(fields=["status", "needed_by"]),
            models.Index(fields=["status", "blood_group"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(hospital__isnull=False) | ~Q(hospital_other=""),
                name="request_has_hospital",
            ),
        ]

    def __str__(self):
        return f"{self.reference} {self.blood_group} x{self.units_needed}"

    # --- validation -------------------------------------------------------

    def clean(self):
        if not self.hospital_id and not self.hospital_other.strip():
            raise ValidationError({"hospital": _("Choose a hospital or type its name.")})
        if self.hospital_id and self.city_id and self.hospital.city_id != self.city_id:
            raise ValidationError({"hospital": _("This hospital is not in the selected city.")})
        if self._state.adding and self.needed_by and self.needed_by < timezone.now():
            raise ValidationError({"needed_by": _("The 'needed by' time must be in the future.")})

    def save(self, *args, **kwargs):
        if self.hospital_id and not self.city_id:
            self.city_id = self.hospital.city_id
        super().save(*args, **kwargs)

    # --- derived ----------------------------------------------------------

    @property
    def hospital_name(self) -> str:
        return self.hospital.name if self.hospital_id else self.hospital_other

    @property
    def location(self):
        """(lat, lng) used for matching: hospital first, then city centre."""
        for source in (self.hospital, self.city):
            if source is not None and source.has_location:
                return source.latitude, source.longitude
        return None

    @property
    def units_donated(self) -> int:
        return self.donations.aggregate(total=Sum("units"))["total"] or 0

    @property
    def units_remaining(self) -> int:
        return max(self.units_needed - self.units_donated, 0)

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    def can_view_contact(self, user) -> bool:
        """Attendant phone is visible to the requester, moderators, and donors
        who accepted this request. Nobody else."""
        if not user.is_authenticated:
            return False
        if user.pk == self.requested_by_id or getattr(user, "is_moderator", False):
            return True
        return self.responses.filter(
            donor__user=user,
            status__in=[DonorResponse.Status.ACCEPTED, DonorResponse.Status.DONATED],
        ).exists()

    # --- state transitions ------------------------------------------------

    def _require(self, *allowed):
        if self.status not in allowed:
            raise InvalidTransition(f"Cannot do this while request is '{self.status}'.")

    def approve(self, moderator):
        self._require(self.Status.PENDING_REVIEW)
        self.status = self.Status.OPEN
        self.reviewed_by = moderator
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])

    def reject(self, moderator, reason: str):
        self._require(self.Status.PENDING_REVIEW, self.Status.OPEN)
        if not reason.strip():
            raise ValueError("A rejection reason is required.")
        self.status = self.Status.REJECTED
        self.reviewed_by = moderator
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason.strip()
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason", "closed_at", "updated_at"])

    def _close(self, status):
        self.status = status
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at", "updated_at"])

    def cancel(self):
        self._require(*self.ACTIVE_STATUSES)
        self._close(self.Status.CANCELLED)

    def mark_fulfilled(self):
        self._require(self.Status.OPEN)
        self._close(self.Status.FULFILLED)

    def expire(self):
        self._require(*self.ACTIVE_STATUSES)
        self._close(self.Status.EXPIRED)


class DonorResponse(TimeStampedModel):
    """One row per donor we contacted (or who volunteered) for a request."""

    class Status(models.TextChoices):
        NOTIFIED = "notified", _("Notified")
        ACCEPTED = "accepted", _("Accepted, on the way")
        DECLINED = "declined", _("Declined")
        DONATED = "donated", _("Donated")
        NO_SHOW = "no_show", _("Did not arrive")
        WITHDRAWN = "withdrawn", _("Withdrew")

    blood_request = models.ForeignKey(BloodRequest, on_delete=models.CASCADE, related_name="responses")
    donor = models.ForeignKey("donors.DonorProfile", on_delete=models.CASCADE, related_name="responses")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOTIFIED)
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    notified_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["blood_request", "distance_km"]
        constraints = [
            models.UniqueConstraint(fields=["blood_request", "donor"], name="one_response_per_donor_per_request"),
        ]

    def __str__(self):
        return f"{self.donor} -> {self.blood_request} ({self.status})"

    def clean(self):
        if self.blood_request_id and self.donor_id and self.donor.user_id == self.blood_request.requested_by_id:
            raise ValidationError(_("You cannot respond to your own request."))

    def _respond(self, status):
        self.status = status
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at", "updated_at"])

    def accept(self):
        if self.blood_request.status != BloodRequest.Status.OPEN:
            raise InvalidTransition("This request is no longer open.")
        if self.status not in (self.Status.NOTIFIED, self.Status.DECLINED):
            raise InvalidTransition(f"Cannot accept from '{self.status}'.")
        self._respond(self.Status.ACCEPTED)

    def decline(self):
        if self.status != self.Status.NOTIFIED:
            raise InvalidTransition(f"Cannot decline from '{self.status}'.")
        self._respond(self.Status.DECLINED)

    def withdraw(self):
        if self.status != self.Status.ACCEPTED:
            raise InvalidTransition(f"Cannot withdraw from '{self.status}'.")
        self._respond(self.Status.WITHDRAWN)
