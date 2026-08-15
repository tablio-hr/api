import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DB_PASSWORD", "unused")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver,127.0.0.1,localhost,tablio-django")

from .base import *  # noqa: E402, F403

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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

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

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
