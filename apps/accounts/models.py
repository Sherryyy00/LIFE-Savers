from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone, password, **extra):
        if not phone:
            raise ValueError("A phone number is required.")
        email = extra.pop("email", "") or ""
        user = self.model(phone=phone, email=self.normalize_email(email), **extra)
        if password:
            user.set_password(password)
        else:
            # Phone + OTP users will not have a password.
            user.set_unusable_password()
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(phone, password, **extra)

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not password:
            raise ValueError("Superusers must have a password.")
        return self._create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Phone number is the login, because many people in the area use WhatsApp
    and SMS far more than email. Email is optional.
    """

    class Role(models.TextChoices):
        MEMBER = "member", _("Member")
        MODERATOR = "moderator", _("Moderator")

    phone = PhoneNumberField(_("phone number"), unique=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    email = models.EmailField(_("email"), blank=True)
    full_name = models.CharField(_("full name"), max_length=100)
    preferred_language = models.CharField(max_length=5, choices=[("en", "English"), ("ur", "اردو")], default="en")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["-date_joined"]
        constraints = [
            # email is optional, but if given it must be unique
            models.UniqueConstraint(fields=["email"], condition=~models.Q(email=""), name="unique_nonblank_email"),
        ]

    def __str__(self):
        return self.full_name or str(self.phone)

    @property
    def is_moderator(self) -> bool:
        return self.is_superuser or self.role == self.Role.MODERATOR

    @property
    def is_phone_verified(self) -> bool:
        return self.phone_verified_at is not None
