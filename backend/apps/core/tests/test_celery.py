from django.test import TestCase

from apps.core.tasks import ping


class CeleryPingTests(TestCase):
    def test_ping_returns_pong(self):
        self.assertEqual(ping(), "pong")
        self.assertEqual(ping.delay().get(), "pong")
