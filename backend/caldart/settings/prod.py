"""Production settings: Apache/nginx -> gunicorn, whitenoise, SMTP email.

Everything host-specific comes from the environment -- in practice from
``/etc/caldart/caldart.env``, loaded by ``deploy/systemd/caldart-web.service``.
Nothing in this chain reads a ``.env`` file: a variable the environment lacks
is a start-up error, not an invitation to take a development value from a file
beside the code.  Four variables have no default on purpose, so a
half-configured box fails at start-up rather than serving with a development
secret: ``SECRET_KEY``, ``ALLOWED_HOSTS``, ``SITE_URL`` and ``EMAIL_URL``.
``docs/developer/configuration.rst`` lists every variable and its production
value.
"""

from copy import deepcopy

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import LOGGING, REPO_ROOT, REST_FRAMEWORK, env

# ``from .base import *`` binds the *same* dict objects as the base module, so
# editing them in place would reach back into whatever settings module is
# already loaded.  Copy the three we change.
DATABASES = deepcopy(DATABASES)  # noqa: F405
LOGGING = deepcopy(LOGGING)
REST_FRAMEWORK = deepcopy(REST_FRAMEWORK)

# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
DEBUG = False

# The key ``base.py`` defaults to and ``.env.example`` ships.  It is published
# in the repository, so a box still running it can have its sessions and
# password-reset links forged by anyone who has read the source.
DEVELOPMENT_SECRET_KEY = "dev-insecure-secret-key-change-me"  # noqa: S105 - already public

# No default: a production box must set its own key, and a missing one is a
# start-up error rather than a quietly shared development secret.
SECRET_KEY = env("SECRET_KEY")
if SECRET_KEY == DEVELOPMENT_SECRET_KEY:
    raise ImproperlyConfigured(
        "SECRET_KEY is still the published development key. Generate one with: "
        'python3 -c "import secrets; print(secrets.token_urlsafe(64))"'
    )

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
SITE_URL = env("SITE_URL")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[SITE_URL])
WAGTAILADMIN_BASE_URL = SITE_URL

# --------------------------------------------------------------------------
# TLS and cookies
#
# Apache/nginx terminate TLS and proxy to gunicorn on loopback; gunicorn only
# trusts X-Forwarded-* from 127.0.0.1 (``forwarded_allow_ips`` in
# deploy/gunicorn.conf.py), so this header cannot be spoofed by a client.
# --------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)

# HSTS: set SECURE_HSTS_SECONDS=0 for the first deploy of a new hostname, then
# raise it once HTTPS is known good -- browsers remember the header for its full
# duration and there is no way to take it back early.  Neither shipped vhost
# sets the header, so this setting is what a browser actually receives.
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
# Off by default: `preload` tells the world the site consents to the browser
# preload list, which no deployment should join by inheriting a default.
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)

# Django owns these on proxied responses too; the vhosts set neither.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# `manage.py check --deploy` reports security.W021 whenever preload is off.
# Leaving it off is the deliberate choice above, so the deployment audit stays
# clean and a real finding is not lost in a known one.
SILENCED_SYSTEM_CHECKS = ["security.W021"]

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
# The portal reads the CSRF cookie from JavaScript and echoes it back as
# X-CSRFToken (see frontend/src/portal/api/client.ts), so this one cannot be
# HttpOnly.  Session hijacking is blocked by SESSION_COOKIE_HTTPONLY above.
CSRF_COOKIE_HTTPONLY = False

# SAMEORIGIN rather than DENY: Wagtail's page previews render the site in an
# iframe inside the admin, and DENY breaks them.  Framing by other origins is
# still refused.
X_FRAME_OPTIONS = "SAMEORIGIN"

# Wagtail image and document uploads.  Keep in step with Apache's
# LimitRequestBody and nginx's client_max_body_size (both 25 MB).
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# --------------------------------------------------------------------------
# Database
#
# Persistent connections: gunicorn workers are long-lived, and reconnecting per
# request to the Postgres container is pure latency.
# --------------------------------------------------------------------------
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# --------------------------------------------------------------------------
# Cache
#
# The auth throttles count in the default cache.  Django's fallback cache is
# per-process, so each of gunicorn's workers would keep a budget of its own and
# reset it whenever the worker recycled.  The database cache is shared by every
# worker and needs no service beyond Postgres -- only `manage.py
# createcachetable`, which the deployment guide runs on install and upgrade.
# --------------------------------------------------------------------------
CACHE_TABLE = "caldart_cache"
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": CACHE_TABLE,
    }
}

# --------------------------------------------------------------------------
# Django REST Framework
#
# Both shipped vhosts pass a client's own X-Forwarded-For through and append the
# address they saw, so only the last entry is trustworthy.  Telling DRF that
# exactly one proxy sits in front makes it read that entry; without it the
# throttles key on the whole header, and a client that varies its prefix is
# never throttled.  gunicorn accepts X-Forwarded-* only from loopback, so the
# proxy is the only thing that can write it.
# --------------------------------------------------------------------------
REST_FRAMEWORK["NUM_PROXIES"] = 1

# --------------------------------------------------------------------------
# Email
#
# No default: reminder and password-reset mail silently going nowhere is worse
# than a start-up error.  Mailpit's smtp://localhost:1025 is a development URL.
# --------------------------------------------------------------------------
vars().update(env.email_url("EMAIL_URL"))
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=20)

# --------------------------------------------------------------------------
# Static files
#
# Compressed *manifest* storage: collectstatic hashes every file name, so the
# far-future cache headers whitenoise sets are safe.  Apache and nginx both
# proxy /static/ through to whitenoise rather than aliasing it, precisely so
# the manifest stays authoritative (see deploy/apache/caldart.conf).
# --------------------------------------------------------------------------
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
WHITENOISE_MAX_AGE = 31536000

# --------------------------------------------------------------------------
# Frontend assets
# --------------------------------------------------------------------------
VITE_DEV_MODE = False
DJANGO_VITE = {
    "default": {
        "dev_mode": False,
        "manifest_path": env(
            "DJANGO_VITE_MANIFEST_PATH",
            default=str(REPO_ROOT / "frontend" / "dist" / ".vite" / "manifest.json"),
        ),
    }
}

# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------
# The mock provider renders "Succeed"/"Fail" buttons, so anyone who can sign in
# can grant themselves a membership.  The development flag, PAYMENTS_MOCK_ENABLED,
# is ignored here: it is on in `.env.example`, and a copied environment file must
# not be what turns it on.  Demonstrating the flow without payment keys takes this
# variable, which exists nowhere else.
PAYMENTS_MOCK_ENABLED = env.bool("PAYMENTS_MOCK_ENABLED_IN_PRODUCTION", default=False)

# --------------------------------------------------------------------------
# Logging
#
# Everything to stdout/stderr: systemd captures it into the journal
# (``journalctl -u caldart-web``), so there are no log files to rotate.
# --------------------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOGGING["root"]["level"] = LOG_LEVEL
LOGGING["handlers"]["mail_admins"] = {
    "class": "django.utils.log.AdminEmailHandler",
    "level": "ERROR",
    "include_html": False,
}
LOGGING["loggers"]["django.request"] = {
    "handlers": ["console", "mail_admins"],
    "level": "ERROR",
    "propagate": False,
}
LOGGING["loggers"]["django.security"] = {
    "handlers": ["console"],
    "level": "WARNING",
    "propagate": False,
}

# Unhandled-500 mail goes here.  Empty is fine: AdminEmailHandler then does
# nothing, and the traceback is still in the journal.
ADMINS = [("CalDART operations", address) for address in env.list("ADMIN_EMAILS", default=[])]
MANAGERS = ADMINS
