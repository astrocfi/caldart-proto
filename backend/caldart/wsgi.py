"""WSGI entrypoint for CalDART."""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.core.wsgi import get_wsgi_application

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# No default: an application server that is not told which settings to load has
# been misconfigured, and falling back to the development settings would serve
# the site with DEBUG on and the published development secret key.
if "DJANGO_SETTINGS_MODULE" not in os.environ:
    raise ImproperlyConfigured(
        "DJANGO_SETTINGS_MODULE is not set. Name the settings module explicitly, "
        "as deploy/systemd/caldart-web.service does with "
        "Environment=DJANGO_SETTINGS_MODULE=caldart.settings.prod."
    )

application = get_wsgi_application()
