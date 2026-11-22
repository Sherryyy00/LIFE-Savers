from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.tests.factories import make_city, make_donor
from apps.donors.models import Donation, DonorProfile


@override_settings(DONATION_INTERVAL_DAYS=90, DONOR_MIN_AGE=18, DONOR_MAX_AGE=60)
class EligibilityTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()

    def test_new_donor_is_eligible(self):
        donor = make_donor()
        self.assertEqual(donor.ineligibility_reasons(), [])
        self.assertIn(donor, DonorProfile.objects.eligible())

    def test_recent_donation_blocks(self):
        donor = make_donor(last_donation_date=self.today - timedelta(days=30))
        self.assertFalse(donor.is_eligible())
        self.assertEqual(donor.next_eligible_date, self.today + timedelta(days=60))
        self.assertNotIn(donor, DonorProfile.objects.eligible())

    def test_interval_boundary(self):
        donor = make_donor(last_donation_date=self.today - timedelta(days=90))
        self.assertTrue(donor.is_eligible())
        self.assertIn(donor, DonorProfile.objects.eligible())

    def test_age_range(self):
        too_old = make_donor(birth_year=self.today.year - 61)
        self.assertFalse(too_old.is_eligible())
        self.assertNotIn(too_old, DonorProfile.objects.eligible())

    def test_paused_and_unavailable(self):
        paused = make_donor(paused_until=self.today + timedelta(days=3))
        off = make_donor(is_available=False)
        eligible = DonorProfile.objects.eligible()
        self.assertNotIn(paused, eligible)
        self.assertNotIn(off, eligible)

    def test_no_consent_or_stale_selfcheck(self):
        no_consent = make_donor(consent_given_at=None)
        stale = make_donor(eligibility_confirmed_at=timezone.now() - timedelta(days=400))
        eligible = DonorProfile.objects.eligible()
        self.assertNotIn(no_consent, eligible)
        self.assertNotIn(stale, eligible)
        self.assertTrue(stale.ineligibility_reasons())

    def test_queryset_matches_python_check(self):
        donors = [
            make_donor(),
            make_donor(last_donation_date=self.today - timedelta(days=10)),
            make_donor(is_available=False),
            make_donor(birth_year=self.today.year - 70),
        ]
        qs_ids = set(DonorProfile.objects.eligible().values_list("id", flat=True))
        py_ids = {d.id for d in donors if d.is_eligible()}
        self.assertEqual(qs_ids, py_ids)


class DonorModelTests(TestCase):
    def test_location_falls_back_to_city(self):
        city = make_city()
        donor = make_donor(city=city)
        self.assertEqual(donor.latitude, city.latitude)

    def test_future_last_donation_invalid(self):
        donor = make_donor()
        donor.last_donation_date = timezone.localdate() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            donor.full_clean()

    def test_donation_updates_last_donation_date(self):
        donor = make_donor()
        d1 = Donation.objects.create(donor=donor, donated_on=timezone.localdate() - timedelta(days=200))
        Donation.objects.create(donor=donor, donated_on=timezone.localdate() - timedelta(days=5))
        donor.refresh_from_db()
        self.assertEqual(donor.last_donation_date, timezone.localdate() - timedelta(days=5))
        donor.donations.order_by("-donated_on").first().delete()
        donor.refresh_from_db()
        self.assertEqual(donor.last_donation_date, d1.donated_on)

    def test_verifying_donation_verifies_blood_group(self):
        from apps.core.tests.factories import make_user

        donor = make_donor()
        donation = Donation.objects.create(donor=donor, donated_on=timezone.localdate())
        donation.verify(make_user())
        donor.refresh_from_db()
        self.assertTrue(donor.blood_group_verified)
