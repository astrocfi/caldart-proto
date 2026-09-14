"""Base Django settings for CalDART.

Every environment variable in ``.env.example`` is read here, with a
development-friendly default so a bare checkout runs without a ``.env``.
``docs/developer/configuration.rst`` documents each one.

Nothing here reads ``.env``: ``dev.py`` and ``test.py`` import ``_dotenv``
before this module, and ``prod.py`` deliberately does not, so a production box
takes its values from the environment alone.
"""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

# backend/caldart/settings/base.py -> repo root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BASE_DIR.parent

env = environ.Env()

# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", default="dev-insecure-secret-key-change-me")
DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])
SITE_URL = env("SITE_URL", default="http://localhost:8000")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[SITE_URL])

WSGI_APPLICATION = "caldart.wsgi.application"
ASGI_APPLICATION = "caldart.asgi.application"
ROOT_URLCONF = "caldart.urls"

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.sites",
]

WAGTAIL_APPS = [
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.settings",
    "wagtail.contrib.styleguide",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_filters",
    "django_vite",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.members",
    "apps.aircraft",
    "apps.payments",
    "apps.reminders",
    "apps.cms",
    "apps.sysadmin",
]

INSTALLED_APPS = DJANGO_APPS + WAGTAIL_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "wagtail.contrib.settings.context_processors.settings",
                "apps.cms.context_processors.site_chrome",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://caldart:caldart@localhost:5432/caldart",
    ),
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/portal/login"
LOGIN_REDIRECT_URL = "/portal/"
LOGOUT_REDIRECT_URL = "/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# i18n / tz
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Los_Angeles"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Static & media
# --------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [REPO_ROOT / "frontend" / "dist"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# --------------------------------------------------------------------------
# django-vite
# --------------------------------------------------------------------------
# Read from the ``DJANGO_VITE_DEV_MODE`` env var.  The value is not
# exported under that name: django-vite treats a top-level
# ``DJANGO_VITE_DEV_MODE`` setting as the deprecated configuration style.
VITE_DEV_MODE = env.bool("DJANGO_VITE_DEV_MODE", default=False)
DJANGO_VITE = {
    "default": {
        "dev_mode": VITE_DEV_MODE,
        "dev_server_host": "localhost",
        "dev_server_port": 5173,
        "manifest_path": REPO_ROOT / "frontend" / "dist" / ".vite" / "manifest.json",
    }
}

# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------
vars().update(env.email_url("EMAIL_URL", default="smtp://localhost:1025"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="CalDART <noreply@caldart.example.org>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# --------------------------------------------------------------------------
# Django REST Framework
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "caldart.authentication.CsrfEnforcingSessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "caldart.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "EXCEPTION_HANDLER": "caldart.exceptions.caldart_exception_handler",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# Rate limits for the anonymous auth endpoints, read by
# ``apps.accounts.throttling``.  A scope mapped to ``None`` is off.
#: The period initials DRF accepts after the slash: second, minute, hour, day.
THROTTLE_PERIOD_INITIALS = ("s", "m", "h", "d")


def _throttle_rate(variable: str, default: str) -> str | None:
    """Read one DRF throttle rate from the environment.

    An unset variable yields ``default``.  A value that is empty or only
    whitespace yields ``None``, which turns that throttle off.  Any other
    value must read ``<count>/<period>`` -- a non-negative whole number, a
    slash, then a period naming or beginning with second, minute, hour or day
    -- and is returned stripped of surrounding whitespace.  A value that DRF
    could not parse raises ``ImproperlyConfigured`` naming the variable, so a
    typo stops start-up instead of turning every request to the throttled
    endpoint into a 500.
    """
    rate = env(variable, default=default).strip()
    if len(rate) == 0:
        return None
    parts = rate.split("/")
    is_valid = (
        len(parts) == 2
        and parts[0].isascii()
        and parts[0].isdigit()
        and parts[1][:1] in THROTTLE_PERIOD_INITIALS
    )
    if not is_valid:
        raise ImproperlyConfigured(
            f"{variable} must be a rate such as '20/min' -- a count, a slash, then "
            f"second, minute, hour or day -- or be empty to turn the throttle off. "
            f"Got {rate!r}."
        )
    return rate


AUTH_THROTTLE_RATES = {
    "auth_login": _throttle_rate("AUTH_THROTTLE_LOGIN", "20/min"),
    "auth_register": _throttle_rate("AUTH_THROTTLE_REGISTER", "10/hour"),
    "auth_password_reset": _throttle_rate("AUTH_THROTTLE_PASSWORD_RESET", "10/hour"),
}

# --------------------------------------------------------------------------
# Wagtail
# --------------------------------------------------------------------------
WAGTAIL_SITE_NAME = "CalDART"
WAGTAILADMIN_BASE_URL = SITE_URL
WAGTAILDOCS_EXTENSIONS = ["csv", "docx", "key", "odt", "pdf", "pptx", "rtf", "txt", "xlsx", "zip"]
# Every document link points at Django's serve view, whatever the storage
# backend, so the members-only hook in apps.cms.wagtail_hooks sees every
# download.  A URL into /media/ would hand the file over without asking.
WAGTAILDOCS_SERVE_METHOD = "serve_view"
WAGTAILIMAGES_EXTENSIONS = ["gif", "jpg", "jpeg", "png", "webp", "svg"]
WAGTAIL_APPEND_SLASH = True
SITE_ID = 1

# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION = env("STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION", default="")
PAYPAL_CLIENT_ID = env("PAYPAL_CLIENT_ID", default="")
PAYPAL_CLIENT_SECRET = env("PAYPAL_CLIENT_SECRET", default="")
PAYPAL_ENV = env("PAYPAL_ENV", default="sandbox")
# Optional: set it to have the PayPal webhook verify its signature.
PAYPAL_WEBHOOK_ID = env("PAYPAL_WEBHOOK_ID", default="")
PAYMENTS_MOCK_ENABLED = env.bool("PAYMENTS_MOCK_ENABLED", default=True)

# --------------------------------------------------------------------------
# sysadmin
# --------------------------------------------------------------------------
BACKUP_DIR = Path(env("BACKUP_DIR", default=str(REPO_ROOT / "backups")))
DB_BACKUP_VIA_DOCKER = env.bool("DB_BACKUP_VIA_DOCKER", default=True)

CALDART_VERSION = "0.1.0"

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "handlers": ["console"], "propagate": False},
    },
}
