"""Test settings: fast hashing, in-memory email and storage, mock payments on."""

from .base import *  # noqa: F403
from .base import LOGGING, REPO_ROOT

DEBUG = False
ALLOWED_HOSTS = ["*", "testserver"]

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

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

WAGTAILADMIN_BASE_URL = "http://testserver"

LOGGING["root"]["level"] = "ERROR"
