import json
import logging
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import IntegrityError, transaction

from apps.leads.models import EarlyAccessLead

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
SUCCESS_PAYLOAD = {"ok": True}


def normalize_email(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().lower()


def upsert_lead(*, name: str, email_normalized: str, interest: str) -> EarlyAccessLead:
    defaults = {"name": name, "interest": interest}
    try:
        with transaction.atomic():
            lead, _created = EarlyAccessLead.objects.update_or_create(
                email_normalized=email_normalized,
                defaults=defaults,
            )
    except IntegrityError:
        lead = EarlyAccessLead.objects.get(email_normalized=email_normalized)
        lead.name = name
        lead.interest = interest
        lead.save(update_fields=["name", "interest", "updated_at"])
    return lead


def notify_early_access(lead: EarlyAccessLead) -> None:
    try:
        _operator_message(lead).send()
    except Exception:
        logger.exception("early-access operator email failed for %s", lead.email_normalized)
    try:
        _applicant_message(lead).send()
    except Exception:
        logger.exception("early-access applicant email failed for %s", lead.email_normalized)


def verify_turnstile(token: str, *, remote_ip: str | None = None) -> bool:
    if not token or not settings.TURNSTILE_SECRET_KEY:
        return False
    payload = {
        "secret": settings.TURNSTILE_SECRET_KEY,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip
    request = urllib.request.Request(
        TURNSTILE_VERIFY_URL,
        data=urllib.parse.urlencode(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        logger.exception("early-access Turnstile verify failed")
        return False
    return bool(body.get("success"))


def client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR")


def _operator_message(lead: EarlyAccessLead) -> EmailMessage:
    body = (
        f"Ime: {lead.name}\n"
        f"E-mail: {lead.email_normalized}\n"
        f"Interes: {lead.interest}\n"
    )
    return EmailMessage(
        subject="Nova prijava za Tablio rani pristup",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.EARLY_ACCESS_NOTIFY_EMAIL],
    )


def _applicant_message(lead: EarlyAccessLead) -> EmailMessage:
    body = (
        f"Poštovani/poštovana {lead.name},\n\n"
        "Primili smo vašu prijavu za rani pristup Tablio platformi. "
        "Javit ćemo se ako vaš objekt bude odabran za pilot.\n\n"
        "Ova poruka je potvrda prijave, ne marketinška obavijest.\n\n"
        "Tablio\n"
        "FINE STAR d.o.o.\n"
    )
    return EmailMessage(
        subject="Primili smo vašu prijavu za Tablio",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[lead.email_normalized],
        reply_to=[settings.EARLY_ACCESS_NOTIFY_EMAIL],
    )
