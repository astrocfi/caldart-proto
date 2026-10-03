"""Base Django settings for CalDART.

Every environment variable in ``.env.example`` outside its production-only section is
read here, with a development-friendly default so a bare checkout runs without a
``.env``.
``docs/developer/configuration.rst`` documents each one.

Nothing here reads ``.env``: ``dev.py`` and ``test.py`` import ``_dotenv``
before this module, and ``prod.py`` deliberately does not, so a production box
takes its values from the environment alone.
"""

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import environ
from csp.constants import SELF, UNSAFE_INLINE
from django.core.exceptions import ImproperlyConfigured

# Absolute, not relative: ``backend/tests/test_auth_throttle_rates.py`` executes this
# module standalone, outside its package, to read the rates a given environment yields.
from caldart.settings.mailers import default_mailer

# backend/caldart/settings/base.py -> repo root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BASE_DIR.parent

env = environ.Env()

#: One segment of ``URL_PREFIX``: the characters a path segment may carry unescaped,
#: less the dots-only segments ``.`` and ``..``, which ``normalize_url_prefix`` refuses.
URL_PREFIX_SEGMENT = re.compile(r"[A-Za-z0-9._~-]+")


def normalize_url_prefix(raw: str) -> str:
    """The URL prefix ``raw`` names, as ``/segment[/segment...]``, or ``""`` for none.

    Surrounding whitespace is ignored, and one leading and one trailing slash are
    optional, so ``caldart-proto``, ``/caldart-proto`` and ``/caldart-proto/`` all read
    as ``/caldart-proto``.  An empty value or a lone ``/`` means the site is served
    from the root of its host.  A prefix with an empty segment (``//x//``), a ``.`` or
    ``..`` segment, or any character other than letters, digits, ``.``, ``_``, ``~``
    and ``-`` raises ``ImproperlyConfigured`` naming ``URL_PREFIX``.
    """
    value = raw.strip().removeprefix("/").removesuffix("/")
    if value == "":
        return ""
    segments = value.split("/")
    for segment in segments:
        if URL_PREFIX_SEGMENT.fullmatch(segment) is None or segment in {".", ".."}:
            raise ImproperlyConfigured(
                f"URL_PREFIX {raw!r} is not a path such as /caldart-proto: each segment "
                "is letters, digits, '.', '_', '~' or '-', with no empty segment."
            )
    return "/" + "/".join(segments)


def site_origin(site_url: str) -> str:
    """The scheme and host of ``site_url``: what a browser sends as ``Origin``."""
    parts = urlsplit(site_url)
    return f"{parts.scheme}://{parts.netloc}"


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", default="dev-insecure-secret-key-change-me")
DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])
SITE_URL = env("SITE_URL", default="http://localhost:8000")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[site_origin(SITE_URL)])

# The path the site is served under when it shares its host with another site, such
# as ``/caldart-proto``; empty when it owns the whole host.  The web server in front
# strips it before proxying, and ``FORCE_SCRIPT_NAME`` makes Django put it back on
# every URL it writes: ``reverse()``, ``{% url %}``, ``static()`` and the media URL.
# ``SITE_URL`` must end in the same path (``prod.py`` refuses a mismatch).  The session
# and CSRF cookies keep the path ``/``: one host runs one CalDART, and the public
# pages beside the portal need the same cookies.
URL_PREFIX = normalize_url_prefix(env("URL_PREFIX", default=""))
FORCE_SCRIPT_NAME = URL_PREFIX or None

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
    # Wagtail's search index stores a SearchVectorField and indexes it with a GinIndex,
    # both of which Django serves only while this app is installed.
    "django.contrib.postgres",
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
    "drf_spectacular",
    "django_filters",
    "django_vite",
    # Installed for its system checks, which catch a misspelled policy setting.
    "csp",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.darts",
    "apps.mail",
    "apps.members",
    "apps.aircraft",
    "apps.payments",
    "apps.reminders",
    "apps.reports",
    "apps.notifications",
    "apps.bulk_email",
    "apps.cms",
    "apps.sysadmin",
]

INSTALLED_APPS = DJANGO_APPS + WAGTAIL_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Response middleware runs bottom-up, so the admin relaxation must sit below
    # CSPMiddleware: it marks the response, CSPMiddleware then writes the header.
    "csp.middleware.CSPMiddleware",
    "caldart.middleware.WagtailAdminCspMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Reads request.user, so it sits below AuthenticationMiddleware.
    "apps.accounts.middleware.EmailVerificationGateMiddleware",
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
LOGIN_URL = f"{URL_PREFIX}/portal/login"
LOGIN_REDIRECT_URL = f"{URL_PREFIX}/portal/"
LOGOUT_REDIRECT_URL = f"{URL_PREFIX}/"

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
# Spelled out with the prefix rather than left relative.  Django would prefix a relative
# ``STATIC_URL`` or ``MEDIA_URL`` with the script name, but only once a request has set
# it, and gunicorn imports the application (and with it the storages, which cache the
# URL) before its first request, so the bundle and upload URLs would miss the prefix.
# whitenoise strips ``FORCE_SCRIPT_NAME`` from ``STATIC_URL`` before matching a path.
STATIC_URL = f"{URL_PREFIX}/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# The built frontend, then the handful of files the templates reference
# directly (the CalDART logo in the masthead).
STATICFILES_DIRS = [REPO_ROOT / "frontend" / "dist", BASE_DIR / "static"]
MEDIA_URL = f"{URL_PREFIX}/media/"
# A server keeps the uploads beside the checkout, in the deploy root, rather than in it.
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))
# The web server serves ``/media/`` straight off disk as its own user, so every
# upload and every directory the site creates under ``MEDIA_ROOT`` must be readable
# by others whatever umask the service runs under (the units use ``UMask=0027``,
# which would otherwise leave a new directory ``0750`` and the web server refused).
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
# A bulk email's images (``apps.bulk_email.images``), stored under ``MEDIA_ROOT`` in
# ``bulk-email/``: the largest file a sender may upload, in bytes (5 MB), and the
# widest an image is stored, in pixels; a wider one is scaled down to it.
BULK_EMAIL_IMAGE_MAX_BYTES = env.int("BULK_EMAIL_IMAGE_MAX_BYTES", default=5 * 1024 * 1024)
BULK_EMAIL_IMAGE_MAX_WIDTH = env.int("BULK_EMAIL_IMAGE_MAX_WIDTH", default=1200)

# The built user guide, which ``caldart.views.user_guide`` serves at ``/docs/``
# to signed-in users.  ``make guide`` writes it here; a deployment that builds
# it elsewhere points this at that directory.
USER_GUIDE_ROOT = Path(env("USER_GUIDE_ROOT", default=str(REPO_ROOT / "docs" / "_build" / "guide")))

# whitenoise's compressed manifest storage, except that Vite's build output keeps the
# names Vite gave it (``caldart.storage``): its chunks import one another by them.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "caldart.storage.ViteManifestStaticFilesStorage",
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
MAILERS = {"default": default_mailer(env.email_url("EMAIL_URL", default="smtp://localhost:1025"))}
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="CalDART <noreply@caldart.example.org>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# The envelope sender (the Return-Path) of every message ``caldart.mail`` sends, where a
# receiving server returns a message it cannot deliver; the ``From`` header stays
# ``DEFAULT_FROM_EMAIL``.  Blank sends the envelope from ``DEFAULT_FROM_EMAIL`` too.
BOUNCE_ADDRESS = env("BOUNCE_ADDRESS", default="")
# The mailbox ``manage.py check_bounces`` reads the returned reports from, as
# ``imaps://user:password@host[:port]/MAILBOX``.  Blank turns bounce checking off.
BOUNCE_IMAP_URL = env("BOUNCE_IMAP_URL", default="")
# The DKIM selector the mail server signs messages with.  ``manage.py check_mail_dns`` and
# the Mail delivery screen look for its public key at ``<selector>._domainkey.<domain>``.
# Blank skips that check with a warning.
DKIM_SELECTOR = env("DKIM_SELECTOR", default="")
# Error reports mask the password in any URL a setting holds, ``BOUNCE_IMAP_URL``
# among them, as well as the settings whose names Django already treats as secret.
DEFAULT_EXCEPTION_REPORTER_FILTER = "caldart.error_reports.CredentialSafeExceptionReporterFilter"
# How long the unsubscribe link in a bulk email keeps working, in seconds: 180 days,
# so a message read months later still turns its type off without signing in.
UNSUBSCRIBE_TOKEN_MAX_AGE = env.int("UNSUBSCRIBE_TOKEN_MAX_AGE", default=15_552_000)

# --------------------------------------------------------------------------
# Bulk email (``apps.bulk_email``)
# --------------------------------------------------------------------------
# The background sender sends at most this many copies a minute, sleeping out the
# rest of each 60 / rate seconds, so a mail provider's rate limit is never reached.
BULK_EMAIL_RATE_PER_MINUTE = env.int("BULK_EMAIL_RATE_PER_MINUTE", default=30)
# The copies sent over one mail connection before the sender opens a fresh one.
BULK_EMAIL_BATCH_SIZE = env.int("BULK_EMAIL_BATCH_SIZE", default=50)
# The undo window: seconds between pressing Send and the first copy, during which the
# send can be canceled.  0 makes a send ready for the sender's next run at once.
BULK_EMAIL_UNDO_SECONDS = env.int("BULK_EMAIL_UNDO_SECONDS", default=120)
# Above this many recipients, Send asks the sender to type the count to confirm it.
BULK_EMAIL_CONFIRM_ABOVE = env.int("BULK_EMAIL_CONFIRM_ABOVE", default=50)

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
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# --------------------------------------------------------------------------
# OpenAPI schema (drf-spectacular)
# --------------------------------------------------------------------------
# The schema is the machine-readable half of the API contract: the backend
# snapshot test and the portal's type test both read it, so every setting here
# is chosen to keep generation deterministic.  ``manage.py spectacular`` writes
# it; no route serves it.
SPECTACULAR_SETTINGS = {
    "TITLE": "CalDART API",
    "DESCRIPTION": "The portal's JSON API.",
    "VERSION": "1.0.0",
    "PREPROCESSING_HOOKS": ["caldart.api_urls.portal_api_endpoints"],
    # The choice labels belong in the API reference, not in a generated
    # description that would churn the snapshot whenever a label is reworded.
    "ENUM_GENERATE_CHOICE_DESCRIPTION": False,
    # Several serializers expose the same choices under the same field name --
    # three different things are called ``status``, and two are called ``type``
    # -- which would otherwise be disambiguated with a hash suffix that changes
    # whenever the set of serializers does.  Naming each choice set here gives
    # every one of them one stable component, whichever serializer reaches it
    # first.
    "ENUM_NAME_OVERRIDES": {
        "PaymentStatusEnum": "apps.payments.models.PaymentStatus.choices",
        "PaymentProviderEnum": "apps.payments.models.PaymentProvider.choices",
        "MembershipStateEnum": "apps.members.models.MembershipState.choices",
        "MembershipTermStatusEnum": "apps.members.models.MembershipStatusChoices.choices",
        "PilotCertificateTypeEnum": "apps.members.models.PilotCertificateType.choices",
        "MedicalTypeEnum": "apps.members.models.MedicalType.choices",
        "PhotoIdTypeEnum": "apps.members.models.PhotoIdType.choices",
        "VerificationItemEnum": "apps.members.verification.ITEM_CHOICES",
        "RolesEnum": "apps.accounts.roles.ROLE_SLUGS",
        "ReminderKindEnum": "apps.reminders.models.ReminderKind.choices",
        "NavKindEnum": "apps.cms.api.serializers.NAV_KINDS",
        "PaymentKindEnum": "apps.payments.models.PaymentKind.choices",
        "MandateProviderEnum": "apps.payments.models.MandateProvider.choices",
        "MandateStatusEnum": "apps.payments.models.MandateStatus.choices",
        "MandateCadenceEnum": "apps.payments.models.MandateCadence.choices",
        "CadenceEnum": "apps.reports.schedule.Cadence.choices",
        "RefundStatusEnum": "apps.payments.models.RefundStatus.choices",
        "RenewalOutcomeEnum": "apps.payments.models.RenewalOutcome.choices",
        "ManualMethodEnum": "apps.payments.manual.MANUAL_METHOD_CHOICES",
        "AccountKindEnum": "apps.accounts.models.AccountKind.choices",
        "PersonKindEnum": "apps.accounts.models.PERSON_KIND_CHOICES",
        "AircraftCategoryEnum": "apps.aircraft.models.AircraftCategory.choices",
        "AirworthinessEnum": "apps.aircraft.models.Airworthiness.choices",
        "BulkEmailRecipientStatusEnum": "apps.bulk_email.models.RecipientStatus.choices",
        "BulkEmailStatusEnum": "apps.bulk_email.models.BulkEmailStatus.choices",
        "RecipientGroupKindEnum": "apps.bulk_email.models.GroupKind.choices",
        # The portal's and the public donation page's mock completions share one set.
        "MockCompleteOutcomeEnum": "apps.payments.api.serializers.MOCK_OUTCOMES",
    },
    # A read-only field and a write-only one describe different objects, so the
    # request body gets its own component; that is the split the portal's
    # ``Profile``/``ProfilePatch`` pairs already make.
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": True,
    "SCHEMA_PATH_PREFIX": "/api/v1",
}

# Rate limits for the auth endpoints, read by
# ``apps.accounts.throttling``.  A scope mapped to ``None`` is off.
#: The period initials DRF accepts after the slash: second, minute, hour, day.
THROTTLE_PERIOD_INITIALS = ("s", "m", "h", "d")


def _throttle_rate(variable: str, default: str) -> str | None:
    """Read one DRF throttle rate from the environment.

    An unset variable yields ``default``.  A value that is empty or only
    whitespace yields ``None``, which turns that throttle off.  Any other
    value must read ``<count>/<period>`` -- a non-negative whole number, a
    slash, then a period naming or beginning with second, minute, hour, or day
    -- and is returned stripped of surrounding whitespace.  A value that DRF
    could not parse raises ``ImproperlyConfigured`` naming the variable, so a
    typo stops start-up instead of turning every request to the throttled
    endpoint into a 500.
    """
    rate: str = env(variable, default=default).strip()
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
            f"second, minute, hour, or day -- or be empty to turn the throttle off. "
            f"Got {rate!r}."
        )
    return rate


AUTH_THROTTLE_RATES = {
    "auth_login": _throttle_rate("AUTH_THROTTLE_LOGIN", "20/min"),
    "auth_register": _throttle_rate("AUTH_THROTTLE_REGISTER", "10/hour"),
    "auth_password_reset": _throttle_rate("AUTH_THROTTLE_PASSWORD_RESET", "10/hour"),
    "auth_verify": _throttle_rate("AUTH_THROTTLE_VERIFY", "30/hour"),
    "auth_verify_resend": _throttle_rate("AUTH_THROTTLE_VERIFY_RESEND", "5/hour"),
    # Starting a gift on the public donation page, which may make a donor account.
    "donate": _throttle_rate("AUTH_THROTTLE_DONATE", "10/hour"),
}

# --------------------------------------------------------------------------
# Address suggestions (Geoapify)
# --------------------------------------------------------------------------
# The key for Geoapify's autocomplete endpoint, which ``apps.members.addresses``
# calls on behalf of the profile form.  Blank turns address suggestions off.
GEOAPIFY_API_KEY = env("GEOAPIFY_API_KEY", default="")
# The autocomplete endpoint itself.  Only the end-to-end run points it elsewhere,
# at a stub that answers a fixed response.
GEOAPIFY_URL = env("GEOAPIFY_URL", default="https://api.geoapify.com/v1/geocode/autocomplete")
# Suggestions a signed-in account may ask for, read by ``apps.members.throttling``.
# ``None`` is off.
ADDRESS_SUGGEST_THROTTLE_RATE = _throttle_rate("ADDRESS_SUGGEST_THROTTLE_RATE", "60/min")

# --------------------------------------------------------------------------
# FAA registry
# --------------------------------------------------------------------------
# Where ``manage.py import_faa_registry`` reads the FAA's Releasable Aircraft
# Database from when no ``--source`` is given: an ``http(s)`` URL of the zip, which
# is downloaded, or a local zip or directory holding ``ACFTREF.txt`` and
# ``MASTER.txt`` (as a path or a ``file://`` URL).  The end-to-end run points it at
# the fixture in ``apps/aircraft/fixtures/faa``.
FAA_REGISTRY_URL = env(
    "FAA_REGISTRY_URL", default="https://registry.faa.gov/database/ReleasableAircraft.zip"
)
# How many minutes an import started from the Health & Database page may run before a
# later press treats it as failed and starts another.
REGISTRY_IMPORT_STALE_MINUTES = env.int("REGISTRY_IMPORT_STALE_MINUTES", default=30)

# How long an email verification link stays usable, in seconds: three days, the
# same as Django's default for a password link.
EMAIL_VERIFICATION_TIMEOUT = env.int("EMAIL_VERIFICATION_TIMEOUT", default=259_200)

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
# Accounts are managed in the portal alone, so Wagtail changes no password or
# address: caldart.urls closes its account screens, and these keep its forms and
# login page from offering what those screens did.
WAGTAIL_PASSWORD_MANAGEMENT_ENABLED = False
WAGTAIL_PASSWORD_RESET_ENABLED = False
WAGTAIL_EMAIL_MANAGEMENT_ENABLED = False
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
# Content-Security-Policy
#
# Enforced rather than report-only: the browser refuses a resource the policy
# does not allow.  ``csp.middleware.CSPMiddleware`` writes the header on every
# response, and ``caldart.middleware.WagtailAdminCspMiddleware`` relaxes
# ``script-src`` for the Wagtail admin alone.
#
# Each vendor list below is copied from that vendor's own published
# Content-Security-Policy page, narrowed to the products this site integrates.
# A vendor that changes its requirements changes these lists.
# --------------------------------------------------------------------------
# Stripe: the "Stripe.js" and "Link" entries of the Content Security Policy
# section of https://docs.stripe.com/security/guide.  Checkout, Connect
# embedded components and the crypto onramp are not used, so their origins are
# absent.  Link is present because ``automatic_payment_methods`` lets the
# Payment Element offer it beside Apple Pay and Google Pay.
STRIPE_SCRIPT_ORIGINS = ["https://js.stripe.com", "https://*.js.stripe.com"]
STRIPE_FRAME_ORIGINS = [
    "https://js.stripe.com",
    "https://*.js.stripe.com",
    # Where a payment method that redirects, 3-D Secure among them, lands.
    "https://hooks.stripe.com",
    "https://link.com",
    "https://*.link.com",
]
STRIPE_CONNECT_ORIGINS = [
    "https://api.stripe.com",
    "https://link.com",
    "https://*.link.com",
]
STRIPE_IMG_ORIGINS = ["https://*.link.com"]

# PayPal: the table at https://developer.paypal.com/sdk/js/csp/, which names
# the same three hosts for ``script-src``, ``frame-src``, ``connect-src`` and
# ``img-src``.  The wildcards cover the live and the sandbox SDK alike, so
# ``PAYPAL_ENV`` can choose between them at run time while the policy is fixed
# at start-up.  That page writes the hosts without a scheme; pinning ``https``
# here keeps the policy from admitting a plaintext copy of an SDK.
PAYPAL_ORIGINS = [
    "https://*.paypal.com",
    "https://*.paypalobjects.com",
    "https://*.venmo.com",
]

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [SELF],
        "script-src": [SELF, *STRIPE_SCRIPT_ORIGINS, *PAYPAL_ORIGINS],
        # ``SELF`` as well as the vendors: Wagtail's admin previews a page in a
        # same-origin frame, which a vendor-only ``frame-src`` would refuse.
        "frame-src": [SELF, *STRIPE_FRAME_ORIGINS, *PAYPAL_ORIGINS],
        "connect-src": [SELF, *STRIPE_CONNECT_ORIGINS, *PAYPAL_ORIGINS],
        # ``data:`` carries the inline SVG icons the portal and the admin draw;
        # the vendor origins carry the wallet and funding-source artwork the
        # Payment Element and the PayPal buttons draw inside their own frames.
        "img-src": [SELF, "data:", *STRIPE_IMG_ORIGINS, *PAYPAL_ORIGINS],
        # The production bundle inlines the Fraunces font faces as ``data:`` URLs
        # (Vite inlines assets under its size limit), which ``default-src`` alone
        # would refuse, leaving every heading in the fallback face.
        "font-src": [SELF, "data:"],
        # Stripe's Payment Element and Wagtail's admin both set styles from
        # JavaScript.  No template carries an inline script, so ``script-src``
        # needs no matching relaxation outside the admin and the user guide,
        # whose Sphinx pages inline the theme's mode switch.
        "style-src": [SELF, UNSAFE_INLINE],
    }
}

# Wagtail draws an account's avatar from Gravatar unless this is ``None``, which
# ``img-src`` refuses; ``None`` makes the admin fall back to the avatar it
# serves from its own static files, and keeps the account's email out of a
# third-party request.
WAGTAIL_GRAVATAR_PROVIDER_URL = None

# --------------------------------------------------------------------------
# sysadmin
# --------------------------------------------------------------------------
BACKUP_DIR = Path(env("BACKUP_DIR", default=str(REPO_ROOT / "backups")))
DB_BACKUP_VIA_DOCKER = env.bool("DB_BACKUP_VIA_DOCKER", default=True)

CALDART_VERSION = "0.1.0"

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
LOGGING: dict[str, Any] = {
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
        # The audit trail carries its own level and handler and stops here, so
        # raising LOG_LEVEL to quiet the application cannot silence it.
        "caldart.audit": {"level": "INFO", "handlers": ["console"], "propagate": False},
        # The HTTP client logs each request's full URL at INFO, and the Geoapify URL
        # carries the API key and a member's typed home address.
        "httpx": {"level": "WARNING"},
        "httpcore": {"level": "WARNING"},
    },
}
