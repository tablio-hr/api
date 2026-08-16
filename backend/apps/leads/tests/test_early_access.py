from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.core import mail
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from apps.leads.models import EarlyAccessLead
from apps.leads.services import normalize_email


@override_settings(SECURE_SSL_REDIRECT=False, TURNSTILE_REQUIRED=False)
class EarlyAccessHttpTests(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox.clear()
        self.host = {"HTTP_HOST": "api.tablio.hr"}

    def _post(self, **body):
        payload = {"name": "Ana Horvat", "email": "ana@x.hr", "interest": "general"}
        payload.update(body)
        return self.client.post(
            "/api/v1/early-access",
            data=payload,
            content_type="application/json",
            **self.host,
        )

    def test_create_persists_normalized_email_and_sends_mail(self):
        response = self._post(email="  Ana@X.HR  ", interest="handheld")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        lead = EarlyAccessLead.objects.get()
        self.assertEqual(lead.name, "Ana Horvat")
        self.assertEqual(lead.email_normalized, "ana@x.hr")
        self.assertEqual(lead.interest, EarlyAccessLead.Interest.HANDHELD)
        self.assertEqual(len(mail.outbox), 2)
        operator, applicant = mail.outbox
        self.assertEqual(operator.to, ["info@tablio.hr"])
        self.assertEqual(operator.from_email, "noreply@tablio.hr")
        self.assertIn("Ana Horvat", operator.body)
        self.assertIn("ana@x.hr", operator.body)
        self.assertIn("handheld", operator.body)
        self.assertEqual(applicant.to, ["ana@x.hr"])
        self.assertEqual(applicant.from_email, "noreply@tablio.hr")
        self.assertEqual(applicant.reply_to, ["info@tablio.hr"])

    def test_resubmit_is_idempotent_and_updates_fields(self):
        first = self._post(name="Ana", email="Ana@X.HR", interest="general")
        second = self._post(name="Ana Marić", email=" ana@x.hr ", interest="handheld")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(EarlyAccessLead.objects.count(), 1)
        lead = EarlyAccessLead.objects.get()
        self.assertEqual(lead.name, "Ana Marić")
        self.assertEqual(lead.interest, EarlyAccessLead.Interest.HANDHELD)
        self.assertEqual(lead.email_normalized, "ana@x.hr")

    def test_nfc_email_collapses_to_one_row(self):
        self._post(email="user@cafe\u0301.hr")
        self._post(email="user@café.hr")
        self.assertEqual(EarlyAccessLead.objects.count(), 1)
        self.assertEqual(EarlyAccessLead.objects.get().email_normalized, "user@café.hr")

    def test_validation_errors(self):
        cases = [
            {"name": "", "email": "ana@x.hr", "interest": "general"},
            {"name": "Ana", "email": "not-an-email", "interest": "general"},
            {"name": "Ana", "email": "ana@x.hr", "interest": "pos"},
        ]
        for payload in cases:
            response = self._post(**payload)
            self.assertEqual(response.status_code, 400, payload)
        self.assertEqual(EarlyAccessLead.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_honeypot_is_silent_success_without_save_or_mail(self):
        response = self._post(website="https://spam.test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(EarlyAccessLead.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_smtp_failure_keeps_lead_and_returns_200(self):
        with patch("apps.leads.services.EmailMessage.send", side_effect=OSError("smtp down")):
            response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(EarlyAccessLead.objects.count(), 1)

    def test_throttle_by_ip(self):
        rest = {
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {"early_access": "1/day"},
        }
        with override_settings(REST_FRAMEWORK=rest):
            first = self._post()
            second = self._post(email="other@x.hr")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

    def test_cors_allowlist(self):
        allowed = self.client.post(
            "/api/v1/early-access",
            data={"name": "Ana", "email": "ana@x.hr", "interest": "general"},
            content_type="application/json",
            HTTP_HOST="api.tablio.hr",
            HTTP_ORIGIN="https://tablio.hr",
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed["Access-Control-Allow-Origin"], "https://tablio.hr")
        denied = self.client.post(
            "/api/v1/early-access",
            data={"name": "Ana", "email": "denied@x.hr", "interest": "general"},
            content_type="application/json",
            HTTP_HOST="api.tablio.hr",
            HTTP_ORIGIN="https://evil.example",
        )
        self.assertEqual(denied.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", denied)
        www = self.client.post(
            "/api/v1/early-access",
            data={"name": "", "email": "bad", "interest": "nope"},
            content_type="application/json",
            HTTP_HOST="api.tablio.hr",
            HTTP_ORIGIN="https://www.tablio.hr",
        )
        self.assertEqual(www.status_code, 400)
        self.assertNotIn("Access-Control-Allow-Origin", www)

    def test_options_preflight_from_marketing_origin(self):
        response = self.client.options(
            "/api/v1/early-access",
            HTTP_HOST="api.tablio.hr",
            HTTP_ORIGIN="https://stage.tablio.hr",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["Access-Control-Allow-Origin"], "https://stage.tablio.hr")
        self.assertIn("POST", response["Access-Control-Allow-Methods"])

    @override_settings(TURNSTILE_REQUIRED=True, TURNSTILE_SECRET_KEY="test-secret")
    def test_turnstile_required_rejects_invalid_token(self):
        with patch("apps.leads.views.verify_turnstile", return_value=False) as verify:
            response = self._post(turnstile_token="bad")
        verify.assert_called_once()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(EarlyAccessLead.objects.count(), 0)

    @override_settings(TURNSTILE_REQUIRED=True, TURNSTILE_SECRET_KEY="test-secret")
    def test_turnstile_required_accepts_valid_token(self):
        with patch("apps.leads.views.verify_turnstile", return_value=True):
            response = self._post(turnstile_token="ok")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EarlyAccessLead.objects.count(), 1)

    def test_model_is_platform_owned(self):
        field_names = {field.name for field in EarlyAccessLead._meta.get_fields()}
        self.assertNotIn("tenant", field_names)
        self.assertNotIn("ip", field_names)
        self.assertNotIn("ip_address", field_names)
        self.assertIn(EarlyAccessLead, admin.site._registry)


class NormalizeEmailTests(SimpleTestCase):
    def test_trim_lower_nfc(self):
        self.assertEqual(normalize_email("  Ana@X.HR  "), "ana@x.hr")
        self.assertEqual(normalize_email("cafe\u0301@x.hr"), "café@x.hr")
