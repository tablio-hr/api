from django.conf import settings

from apps.tenants.tokens import display_prefix, generate_token, hash_token, verify_token

__all__ = [
    "display_prefix",
    "generate_staff_token",
    "hash_token",
    "is_staff_token",
    "staff_token_prefix",
    "verify_token",
]


def staff_token_prefix() -> str:
    return getattr(settings, "TABLIO_STAFF_TOKEN_PREFIX", "tablio_st_")


def generate_staff_token() -> str:
    return generate_token(staff_token_prefix())


def is_staff_token(token: str) -> bool:
    return token.startswith(staff_token_prefix())
