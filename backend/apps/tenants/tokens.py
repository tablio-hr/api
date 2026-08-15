import hashlib
import secrets

from django.conf import settings

TOKEN_SUFFIX_BYTES = 32
KEY_PREFIX_DISPLAY_LEN = 16


def default_key_prefix() -> str:
    return getattr(settings, "TABLIO_API_KEY_PREFIX", "tablio_pk_test_")


def generate_token(prefix: str | None = None) -> str:
    return f"{prefix or default_key_prefix()}{secrets.token_urlsafe(TOKEN_SUFFIX_BYTES)}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, stored_hash: str) -> bool:
    return secrets.compare_digest(hash_token(token), stored_hash)


def display_prefix(token: str) -> str:
    return token[:KEY_PREFIX_DISPLAY_LEN]


def extract_token_from_request(request) -> str | None:
    authorization = request.META.get("HTTP_AUTHORIZATION", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    header_key = request.META.get("HTTP_X_TABLIO_APP_KEY", "").strip()
    if header_key:
        return header_key
    return None
