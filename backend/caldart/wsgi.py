"""WSGI entrypoint for CalDART."""

import os
import sys
from pathlib import Path

from django.core.wsgi import get_wsgi_application

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caldart.settings.dev")

application = get_wsgi_application()
