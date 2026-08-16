import unicodedata


def normalize_primary_login(value: str) -> str:
    cleaned = unicodedata.normalize("NFKC", value).replace("\ufeff", "")
    return cleaned.strip().casefold()
