from django.test import SimpleTestCase

from apps.core.blood import can_donate_to, compatible_donor_groups, match_priority
from apps.core.geo import bounding_box, haversine_km


class CompatibilityTests(SimpleTestCase):
    def test_universal_donor_and_recipient(self):
        for group in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]:
            self.assertTrue(can_donate_to("O-", group))
        self.assertEqual(len(compatible_donor_groups("AB+")), 8)
        self.assertEqual(compatible_donor_groups("O-"), {"O-"})

    def test_rh_negative_cannot_receive_positive(self):
        for neg in ["A-", "B-", "AB-", "O-"]:
            self.assertFalse(any(g.endswith("+") for g in compatible_donor_groups(neg)))

    def test_known_incompatibilities(self):
        self.assertFalse(can_donate_to("A+", "B+"))
        self.assertFalse(can_donate_to("AB-", "A-"))
        self.assertTrue(can_donate_to("B-", "AB+"))

    def test_unknown_group(self):
        with self.assertRaises(ValueError):
            compatible_donor_groups("C+")

    def test_priority(self):
        self.assertEqual(match_priority("B+", "B+"), 0)
        self.assertEqual(match_priority("O+", "B+"), 1)
        self.assertEqual(match_priority("O-", "B+"), 2)


class GeoTests(SimpleTestCase):
    def test_wah_to_taxila_distance(self):
        d = haversine_km(33.7833, 72.7167, 33.7458, 72.7875)
        self.assertTrue(6 < d < 9, d)

    def test_bounding_box_contains_centre(self):
        box = bounding_box(33.78, 72.71, 10)
        self.assertLess(box.min_lat, 33.78)
        self.assertGreater(box.max_lng, 72.71)
