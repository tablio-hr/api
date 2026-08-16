import os

os.environ.setdefault("DJANGO_SECRET_KEY", "ci-secret-key-not-for-production")
os.environ.setdefault("DB_PASSWORD", "tablio")

from .base import *  # noqa: E402, F403
from .base import env

DEBUG = False
SECRET_KEY = "ci-secret-key-not-for-production"
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="tablio_platform_test_db"),
        "USER": env("DB_USER", default="tablio"),
        "PASSWORD": env("DB_PASSWORD", default="tablio"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
    }
}

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
TURNSTILE_REQUIRED = False

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
