"""Development settings: DEBUG on, mock payments, Mailpit for email.

Importing ``_dotenv`` first is what loads the repository's ``.env``, so every
default below sees the values a checkout keeps there.
"""

from copy import deepcopy

from csp.constants import UNSAFE_INLINE

from . import _dotenv  # noqa: F401  (imported for its side effect: it reads .env)
from .base import *  # noqa: F403
from .base import CONTENT_SECURITY_POLICY, DJANGO_VITE, env

DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])
INTERNAL_IPS = ["127.0.0.1"]

# Hashed/manifest static storage is unhelpful while iterating.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# --------------------------------------------------------------------------
# Content-Security-Policy
#
# With ``DJANGO_VITE_DEV_MODE=true`` the shells load their modules from the Vite
# dev server instead of ``frontend/dist``: the modules and the HMR client come
# over HTTP from that origin, the update socket over ``ws://``, and django-vite
# writes React Fast Refresh's preamble as an inline script.  Those four
# allowances belong to this settings module alone -- production serves built
# assets from ``/static/`` under the base policy.
#
# ``from .base import *`` binds the base module's own dict, so copy it before
# editing rather than reaching back into whatever else imported it.
# --------------------------------------------------------------------------
VITE_DEV_AUTHORITY = (
    f"{DJANGO_VITE['default']['dev_server_host']}:{DJANGO_VITE['default']['dev_server_port']}"
)
VITE_DEV_SERVER = f"http://{VITE_DEV_AUTHORITY}"
VITE_HMR_SOCKET = f"ws://{VITE_DEV_AUTHORITY}"

CONTENT_SECURITY_POLICY = deepcopy(CONTENT_SECURITY_POLICY)
_directives = CONTENT_SECURITY_POLICY["DIRECTIVES"]
_directives["default-src"] += [VITE_DEV_SERVER]
_directives["script-src"] += [VITE_DEV_SERVER, UNSAFE_INLINE]
_directives["connect-src"] += [VITE_DEV_SERVER, VITE_HMR_SOCKET]
_directives["img-src"] += [VITE_DEV_SERVER]
