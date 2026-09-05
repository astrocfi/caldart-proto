"""Production settings: Apache/nginx -> gunicorn, whitenoise, SMTP email."""

from .base import *  # noqa: F403
from .base import LOGGING, REPO_ROOT, env

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[env("SITE_URL")])

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

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

PAYMENTS_MOCK_ENABLED = env.bool("PAYMENTS_MOCK_ENABLED", default=False)

LOGGING["root"]["level"] = env("LOG_LEVEL", default="INFO")
