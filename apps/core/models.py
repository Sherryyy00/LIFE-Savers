from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

LAT_VALIDATORS = [MinValueValidator(-90), MaxValueValidator(90)]
LNG_VALIDATORS = [MinValueValidator(-180), MaxValueValidator(180)]


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class LocatedModel(models.Model):
    """Optional lat/lng pair, ~10 cm precision."""

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=LAT_VALIDATORS)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=LNG_VALIDATORS)

    class Meta:
        abstract = True

    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None


class City(TimeStampedModel, LocatedModel):
    name = models.CharField(_("name"), max_length=80, unique=True)
    name_ur = models.CharField(_("name (Urdu)"), max_length=80, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "cities"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Area(TimeStampedModel, LocatedModel):
    """A sector, mohalla or colony inside a city. Managed from the admin."""

    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="areas")
    name = models.CharField(_("name"), max_length=100)
    name_ur = models.CharField(_("name (Urdu)"), max_length=100, blank=True)

    class Meta:
        ordering = ["city__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["city", "name"], name="unique_area_per_city"),
        ]

    def __str__(self):
        return f"{self.name}, {self.city}"


class Hospital(TimeStampedModel, LocatedModel):
    name = models.CharField(_("name"), max_length=150)
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="hospitals")
    address = models.CharField(_("address"), max_length=255, blank=True)
    phone = PhoneNumberField(_("phone"), blank=True)
    has_blood_bank = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False, help_text=_("Checked by a moderator as a real hospital."))

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "city"], name="unique_hospital_per_city"),
        ]

    def __str__(self):
        return f"{self.name} ({self.city})"
