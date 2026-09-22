"""Test settings: fast hashing, in-memory email and storage, mock payments on.

Importing ``_dotenv`` first is what loads the repository's ``.env``, so a
worktree's own ``DATABASE_URL`` reaches the test database name.
"""

import tempfile
from pathlib import Path

from . import _dotenv  # noqa: F401  (imported for its side effect: it reads .env)
from .base import *  # noqa: F403
from .base import AUTH_THROTTLE_RATES, LOGGING, REPO_ROOT, env

DEBUG = False
ALLOWED_HOSTS = ["*", "testserver"]

# WhiteNoise warns when STATIC_ROOT does not exist on disk, and the suite never
# runs collectstatic.  Pointing STATIC_ROOT at a directory this import creates
# keeps that warning from firing at all, rather than silencing it.
STATIC_ROOT = Path(tempfile.mkdtemp(prefix="caldart-staticfiles-"))

# Throttles are inert under test; the throttling test turns one back on with
# ``override_settings`` rather than every other test racing a shared counter.
AUTH_THROTTLE_RATES = dict.fromkeys(AUTH_THROTTLE_RATES, None)

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}

PAYMENTS_MOCK_ENABLED = True

VITE_DEV_MODE = False
# ``conftest.py`` points this at a stub manifest it builds outside the
# checkout unless the environment already names one (CI's backend job sets it
# to the real build's manifest for the tests marked ``needs_frontend_build``).
DJANGO_VITE = {
    "default": {
        "dev_mode": False,
        "manifest_path": env.path(
            "DJANGO_VITE_MANIFEST_PATH",
            default=REPO_ROOT / "frontend" / "dist" / ".vite" / "manifest.json",
        ),
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
