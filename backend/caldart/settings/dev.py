"""Development settings: DEBUG on, mock payments, Mailpit for email."""

from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])
INTERNAL_IPS = ["127.0.0.1"]

# Hashed/manifest static storage is unhelpful while iterating.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
