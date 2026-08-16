from django.test import SimpleTestCase

from apps.identity.login import normalize_primary_login


class NormalizePrimaryLoginTests(SimpleTestCase):
    def test_trim_and_casefold(self):
        self.assertEqual(normalize_primary_login("  User@X.HR  "), "user@x.hr")

    def test_nfkc(self):
        self.assertEqual(normalize_primary_login("\ufeffadmin@x.hr"), "admin@x.hr")
