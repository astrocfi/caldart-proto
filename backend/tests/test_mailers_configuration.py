"""The ``EMAIL_URL`` variable and the ``MAILERS`` setting it produces.

Django configures outgoing mail through ``MAILERS``, a dict of named mailers, while
the deployment interface stays a single ``EMAIL_URL``.  ``caldart.settings.mailers``
translates one into the other, and these tests pin that translation: which options
each backend receives, which it refuses, and that Django can build the result.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.locmem import EmailBackend as LocMemEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend
from pytest_django import Settings

from caldart.settings.mailers import CONSOLE_BACKEND, FILE_BACKEND, SMTP_BACKEND, default_mailer


def email_url_settings(**overrides: Any) -> dict[str, Any]:
    """An ``env.email_url`` result for an SMTP URL, with the given keys replaced.

    django-environ always returns ``EMAIL_BACKEND``, ``EMAIL_FILE_PATH``,
    ``EMAIL_HOST``, ``EMAIL_PORT``, ``EMAIL_HOST_USER`` and ``EMAIL_HOST_PASSWORD``,
    and adds ``EMAIL_USE_TLS`` or ``EMAIL_USE_SSL`` only for a ``+tls`` or ``+ssl``
    scheme.  An absent value arrives as ``None`` or as the empty string.
    """
    parsed: dict[str, Any] = {
        "EMAIL_BACKEND": SMTP_BACKEND,
        "EMAIL_FILE_PATH": "",
        "EMAIL_HOST": "smtp.example.org",
        "EMAIL_PORT": 587,
        "EMAIL_HOST_USER": "caldart@example.org",
        "EMAIL_HOST_PASSWORD": "hunter2",
    }
    parsed.update(overrides)
    return parsed


def test_an_smtp_url_becomes_the_connection_options() -> None:
    """Host, port, username and password reach the SMTP backend as ``OPTIONS``."""
    assert default_mailer(email_url_settings()) == {
        "BACKEND": SMTP_BACKEND,
        "OPTIONS": {
            "host": "smtp.example.org",
            "port": 587,
            "username": "caldart@example.org",
            "password": "hunter2",
        },
    }


def test_a_tls_url_turns_on_use_tls() -> None:
    """A ``smtp+tls://`` URL adds ``use_tls`` to the options."""
    mailer = default_mailer(email_url_settings(EMAIL_USE_TLS=True))

    assert mailer["OPTIONS"]["use_tls"] is True


def test_an_unauthenticated_url_omits_the_credentials() -> None:
    """A URL without a user or password leaves both options out."""
    mailer = default_mailer(
        email_url_settings(
            EMAIL_HOST="localhost",
            EMAIL_PORT=1025,
            EMAIL_HOST_USER=None,
            EMAIL_HOST_PASSWORD=None,
        )
    )

    assert mailer["OPTIONS"] == {"host": "localhost", "port": 1025}


def test_a_timeout_becomes_an_smtp_option() -> None:
    """``timeout`` is passed through as the SMTP socket timeout in seconds."""
    mailer = default_mailer(email_url_settings(), timeout=20)

    assert mailer["OPTIONS"]["timeout"] == 20


def test_the_console_backend_takes_no_options() -> None:
    """``consolemail://`` names the console backend and carries nothing else."""
    parsed = email_url_settings(
        EMAIL_BACKEND=CONSOLE_BACKEND,
        EMAIL_HOST=None,
        EMAIL_PORT=None,
        EMAIL_HOST_USER=None,
        EMAIL_HOST_PASSWORD=None,
    )

    assert default_mailer(parsed, timeout=20) == {"BACKEND": CONSOLE_BACKEND}


def test_the_file_backend_keeps_only_its_path() -> None:
    """``filemail://`` passes the directory through as the ``file_path`` option."""
    parsed = email_url_settings(
        EMAIL_BACKEND=FILE_BACKEND,
        EMAIL_FILE_PATH="/var/spool/caldart",
        EMAIL_HOST=None,
        EMAIL_PORT=None,
        EMAIL_HOST_USER=None,
        EMAIL_HOST_PASSWORD=None,
    )

    assert default_mailer(parsed) == {
        "BACKEND": FILE_BACKEND,
        "OPTIONS": {"file_path": "/var/spool/caldart"},
    }


def test_the_test_settings_send_to_the_in_memory_outbox() -> None:
    """The suite's default mailer is the locmem backend that fills ``mail.outbox``."""
    assert isinstance(mail.mailers.default, LocMemEmailBackend)


def test_django_builds_the_smtp_backend_an_email_url_describes(settings: Settings) -> None:
    """Every option an ``EMAIL_URL`` yields is one the SMTP backend accepts.

    An option the backend does not know raises ``InvalidMailer`` as it is built, so
    building it is what proves the translation names the options correctly.
    """
    settings.MAILERS = {
        "default": default_mailer(email_url_settings(EMAIL_USE_TLS=True), timeout=20)
    }

    mailer = mail.mailers.default

    assert isinstance(mailer, SMTPEmailBackend)
    assert mailer.timeout == 20


def test_an_unknown_backend_is_rejected() -> None:
    """A backend the options table does not list stops the settings from loading."""
    parsed = email_url_settings(EMAIL_BACKEND="caldart.mail.NoSuchBackend")

    with pytest.raises(ImproperlyConfigured, match=r"caldart\.mail\.NoSuchBackend"):
        default_mailer(parsed)
