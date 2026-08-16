import os

from django.core.exceptions import ImproperlyConfigured

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver,127.0.0.1,localhost,tablio-django")

from .base import *  # noqa: E402, F403
from .base import env

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"
ALLOWED_HOSTS = [
    "testserver",
    "127.0.0.1",
    "localhost",
    "tablio-django",
    "admin.tablio.hr",
    "admin-stage.tablio.hr",
    "api.tablio.hr",
    "api-stage.tablio.hr",
]
CSRF_TRUSTED_ORIGINS = [
    "https://admin.tablio.hr",
    "https://admin-stage.tablio.hr",
]

# Tests run only on PostgreSQL/PostGIS — the same engine as production and PR CI.
# Django creates a throwaway `test_*` database from this connection; it does not
# run assertions against the live NAME.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="tablio_platform_test_db"),
        "USER": env("DB_USER", default="tablio"),
        "PASSWORD": env("DB_PASSWORD", default="tablio"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
        "CONN_MAX_AGE": 0,
    }
}

if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("Tablio tests run only on PostgreSQL/PostGIS.")

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
REDIS_URL = "redis://invalid-redis-for-tests:6379/4"
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
TURNSTILE_REQUIRED = False

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
