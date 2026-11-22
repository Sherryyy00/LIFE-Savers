from django.test import TestCase
from django.urls import reverse


class ViewTests(TestCase):
    def test_home(self):
        r = self.client.get(reverse("core:home"))
        self.assertContains(r, "LIFE Savers")
        self.assertContains(r, "Every Drop Counts")

    def test_healthz(self):
        r = self.client.get(reverse("core:healthz"))
        self.assertEqual(r.json(), {"status": "ok"})

    def test_default_admin_path_not_exposed(self):
        self.assertEqual(self.client.get("/admin/").status_code, 404)
