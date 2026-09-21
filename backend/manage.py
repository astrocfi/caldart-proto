#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from pathlib import Path


def main() -> None:
    """Run a Django management command, defaulting to the ``dev`` settings module.

    Adds this file's directory to ``sys.path`` so ``caldart`` imports regardless of the
    working directory, then delegates to Django's ``execute_from_command_line`` with
    ``sys.argv``. Raises ``ImportError`` with a setup hint when Django is not installed.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caldart.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - developer ergonomics
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and available on your "
            "PYTHONPATH environment variable? Did you forget to run `uv sync`?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
