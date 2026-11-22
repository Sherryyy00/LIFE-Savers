from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User


class UserTests(TestCase):
    def test_local_number_is_normalised_to_e164(self):
        user = User.objects.create_user(phone="0300 1234567", full_name="Ali")
        user.refresh_from_db()
        self.assertEqual(str(user.phone), "+923001234567")
        self.assertFalse(user.has_usable_password())

    def test_phone_unique(self):
        User.objects.create_user(phone="+923001234567", full_name="A")
        with self.assertRaises((ValidationError, IntegrityError)):
            User.objects.create_user(phone="03001234567", full_name="B")

    def test_invalid_phone_rejected(self):
        with self.assertRaises(ValidationError):
            User.objects.create_user(phone="12345", full_name="X")

    def test_blank_emails_do_not_clash_but_real_ones_do(self):
        User.objects.create_user(phone="+923001111111", full_name="A")
        User.objects.create_user(phone="+923002222222", full_name="B")
        User.objects.create_user(phone="+923003333333", full_name="C", email="c@example.com")
        with self.assertRaises((ValidationError, IntegrityError)):
            User.objects.create_user(phone="+923004444444", full_name="D", email="c@example.com")

    def test_superuser_needs_password(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(phone="+923005555555", full_name="Admin")
        admin = User.objects.create_superuser(phone="+923005555555", full_name="Admin", password="x-Strong-pass-9")
        self.assertTrue(admin.is_moderator)
