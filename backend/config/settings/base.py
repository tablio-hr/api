from pathlib import Path

import environ

from config.hosts import TABLIO_ADMIN_HOSTS, TABLIO_API_HOSTS, TABLIO_INTERNAL_HOSTS

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["127.0.0.1", "localhost", "tablio-django"]),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    DB_CONN_MAX_AGE=(int, 60),
    TABLIO_STAFF_SESSION_TTL_HOURS=(int, 12),
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS")

TABLIO_ADMIN_HOST = env("TABLIO_ADMIN_HOST", default="admin-stage.tablio.hr")
TABLIO_API_HOST = env("TABLIO_API_HOST", default="api-stage.tablio.hr")
TABLIO_API_KEY_PREFIX = env("TABLIO_API_KEY_PREFIX", default="tablio_pk_test_")
TABLIO_STAFF_TOKEN_PREFIX = env("TABLIO_STAFF_TOKEN_PREFIX", default="tablio_st_")
TABLIO_STAFF_SESSION_TTL_HOURS = env("TABLIO_STAFF_SESSION_TTL_HOURS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core",
    "apps.tenants",
    "apps.identity",
    "apps.api",
]

MIDDLEWARE = [
    "apps.core.middleware.TablioSecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.core.middleware.HostIsolationMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.tenants.middleware.TenantHostMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="tablio_platform_db"),
        "USER": env("DB_USER", default="tablio"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="postgis"),
        "PORT": env("DB_PORT", default="5432"),
        "CONN_MAX_AGE": env("DB_CONN_MAX_AGE"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "hr"
TIME_ZONE = "Europe/Zagreb"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.api.authentication.AppKeyAuthentication",
    ],
    "EXCEPTION_HANDLER": "apps.api.exceptions.exception_handler",
    "UNAUTHENTICATED_USER": None,
}

REDIS_URL = env("REDIS_URL", default="redis://infra-redis:6379/4")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = False

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "sensitive_headers": {
            "()": "apps.core.logging.SensitiveHeaderFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["sensitive_headers"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

# Re-export host frozensets for settings access
TABLIO_ADMIN_HOSTS = TABLIO_ADMIN_HOSTS
TABLIO_API_HOSTS = TABLIO_API_HOSTS
TABLIO_INTERNAL_HOSTS = TABLIO_INTERNAL_HOSTS
