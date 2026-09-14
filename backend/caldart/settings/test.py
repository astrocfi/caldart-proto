"""Test settings: fast hashing, in-memory email and storage, mock payments on."""

from .base import *  # noqa: F403
from .base import AUTH_THROTTLE_RATES, LOGGING, REPO_ROOT

DEBUG = False
ALLOWED_HOSTS = ["*", "testserver"]

# Throttles are inert under test; the throttling test turns one back on with
# ``override_settings`` rather than every other test racing a shared counter.
AUTH_THROTTLE_RATES = dict.fromkeys(AUTH_THROTTLE_RATES, None)

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

PAYMENTS_MOCK_ENABLED = True

VITE_DEV_MODE = False
DJANGO_VITE = {
    "default": {
        "dev_mode": False,
        "manifest_path": REPO_ROOT / "frontend" / "dist" / ".vite" / "manifest.json",
    }
}

# `make check-backend` runs Django's system checks under these settings with
# --fail-level WARNING, and the backend CI job does not build the frontend, so
# frontend/dist is absent there.  These two checks only report that missing build.
SILENCED_SYSTEM_CHECKS = ["django_vite.W001", "staticfiles.W004"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

WAGTAILADMIN_BASE_URL = "http://testserver"

LOGGING["root"]["level"] = "ERROR"
