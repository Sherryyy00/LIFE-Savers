from datetime import timedelta
from io import StringIO

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.blood_requests.matching import create_notifications, find_matching_donors
from apps.blood_requests.models import BloodRequest, DonorResponse, InvalidTransition
from apps.core.tests.factories import make_city, make_donor, make_hospital, make_request, make_user

# Points around Wah Cantt hospital (33.7833, 72.7167)
NEAR = ("33.790000", "72.720000")  # under 1 km
MEDIUM = ("33.745800", "72.787500")  # Taxila, about 8 km
FAR = ("33.684400", "73.047900")  # Islamabad, about 32 km


class MatchingTests(TestCase):
    def setUp(self):
        self.city = make_city()
        self.hospital = make_hospital(self.city)

    def test_compatible_nearby_ranked(self):
        exact_far = make_donor("B-", self.city, *MEDIUM)
        exact_near = make_donor("B-", self.city, *NEAR)
        universal = make_donor("O-", self.city, *NEAR)
        make_donor("B+", self.city, *NEAR)  # incompatible with B-
        make_donor("B-", self.city, *FAR)  # outside radius
        br = make_request("B-", self.hospital)
        result = [m.donor for m in find_matching_donors(br, radius_km=15)]
        self.assertEqual(result, [exact_near, exact_far, universal])

    def test_excludes_requester_and_ineligible(self):
        requester = make_user()
        make_donor("A+", self.city, *NEAR, user=requester)
        make_donor("A+", self.city, *NEAR, last_donation_date=timezone.localdate())
        br = make_request("A+", self.hospital, requested_by=requester)
        self.assertEqual(find_matching_donors(br), [])

    def test_already_notified_donors_skipped(self):
        donor = make_donor("AB+", self.city, *NEAR)
        br = make_request("AB+", self.hospital)
        br.approve(make_user())
        create_notifications(br, find_matching_donors(br))
        self.assertTrue(DonorResponse.objects.filter(blood_request=br, donor=donor).exists())
        self.assertEqual(find_matching_donors(br), [])

    def test_cannot_notify_unapproved(self):
        br = make_request("O+", self.hospital)
        with self.assertRaises(ValueError):
            create_notifications(br, [])


class RequestLifecycleTests(TestCase):
    def setUp(self):
        self.mod = make_user(full_name="Mod")
        self.br = make_request()

    def test_starts_pending_and_has_reference(self):
        self.assertEqual(self.br.status, BloodRequest.Status.PENDING_REVIEW)
        self.assertRegex(self.br.reference, r"^LS-[A-Z2-9]{6}$")

    def test_approve_then_fulfil(self):
        self.br.approve(self.mod)
        self.br.mark_fulfilled()
        self.assertEqual(self.br.status, BloodRequest.Status.FULFILLED)
        self.assertIsNotNone(self.br.closed_at)

    def test_cannot_fulfil_pending(self):
        with self.assertRaises(InvalidTransition):
            self.br.mark_fulfilled()

    def test_reject_needs_reason(self):
        with self.assertRaises(ValueError):
            self.br.reject(self.mod, " ")
        self.br.reject(self.mod, "Could not verify with hospital")
        self.assertEqual(self.br.status, BloodRequest.Status.REJECTED)

    def test_past_needed_by_invalid_on_create(self):
        br = BloodRequest(
            requested_by=make_user(),
            patient_label="X",
            blood_group="A+",
            hospital=self.br.hospital,
            city=self.br.city,
            attendant_phone="+923001234567",
            needed_by=timezone.now() - timedelta(hours=1),
        )
        with self.assertRaises(ValidationError):
            br.full_clean()

    def test_hospital_required(self):
        br = BloodRequest(
            requested_by=make_user(),
            patient_label="X",
            blood_group="A+",
            city=self.br.city,
            attendant_phone="+923001234567",
            needed_by=timezone.now() + timedelta(hours=1),
        )
        with self.assertRaises(ValidationError):
            br.full_clean()

    def test_overdue_requests_expire(self):
        BloodRequest.objects.filter(pk=self.br.pk).update(needed_by=timezone.now() - timedelta(minutes=1))
        from django.core.management import call_command

        call_command("expire_requests", stdout=StringIO())
        self.br.refresh_from_db()
        self.assertEqual(self.br.status, BloodRequest.Status.EXPIRED)


class ContactPrivacyTests(TestCase):
    def setUp(self):
        city = make_city()
        self.br = make_request("B+", make_hospital(city))
        self.br.approve(make_user())
        self.donor = make_donor("B+", city, *NEAR)
        self.response = DonorResponse.objects.create(blood_request=self.br, donor=self.donor)

    def test_contact_hidden_until_accept(self):
        stranger = make_user()
        self.assertFalse(self.br.can_view_contact(stranger))
        self.assertFalse(self.br.can_view_contact(self.donor.user))
        self.response.accept()
        self.assertTrue(self.br.can_view_contact(self.donor.user))
        self.assertTrue(self.br.can_view_contact(self.br.requested_by))

    def test_cannot_accept_closed_request(self):
        self.br.cancel()
        with self.assertRaises(InvalidTransition):
            self.response.accept()

    def test_donor_cannot_respond_to_own_request(self):
        own = DonorResponse(blood_request=self.br, donor=make_donor("B+", user=self.br.requested_by))
        with self.assertRaises(ValidationError):
            own.full_clean()
