from unittest.mock import patch

from django.db import connection
from django.test import TestCase, override_settings


class HealthReadyTests(TestCase):
    def test_health_ok_without_database(self):
        with patch.object(connection, "cursor", side_effect=RuntimeError("db down")):
            response = self.client.get("/health/", HTTP_HOST="127.0.0.1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_ready_503_when_redis_down(self):
        response = self.client.get("/ready/", HTTP_HOST="127.0.0.1")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "unavailable")
        self.assertEqual(response.json()["checks"]["redis"], "unavailable")

    def test_ready_503_when_database_down(self):
        with patch.object(connection, "cursor", side_effect=RuntimeError("db down")):
            response = self.client.get("/ready/", HTTP_HOST="127.0.0.1")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["checks"]["database"], "unavailable")

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_internal_ready_does_not_redirect(self):
        response = self.client.get("/ready/", HTTP_HOST="127.0.0.1")
        self.assertNotEqual(response.status_code, 301)
        self.assertIn(response.status_code, (200, 503))

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_public_ready_still_redirects(self):
        response = self.client.get("/ready/", HTTP_HOST="api.tablio.hr")
        self.assertEqual(response.status_code, 301)
