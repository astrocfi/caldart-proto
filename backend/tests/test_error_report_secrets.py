"""Error reports never carry the bounce mailbox's password.

Django's error reports (the mail sent to ``ADMIN_EMAILS``) list the settings and each
frame's variables.  ``caldart.error_reports.CredentialSafeExceptionReporterFilter``
masks the password in any URL a setting holds, and the bounce check's frames are
marked sensitive.  See ``docs/developer/configuration.rst``.
"""

from __future__ import annotations

import sys

import pytest
from django.views.debug import ExceptionReporter
from pytest_django import Settings

from apps.mail.bounces import BounceCheckError, check_bounces, parse_imap_url
from caldart.error_reports import CredentialSafeExceptionReporterFilter
from tests.conftest import FAKE_BOUNCE_IMAP_URL, FakeMailbox

pytestmark = pytest.mark.django_db

#: The password :data:`FAKE_BOUNCE_IMAP_URL` carries.
PASSWORD = "s3cret"  # noqa: S105 - the fake mailbox's stand-in password


def _report(exc: BaseException) -> str:
    """The plain-text error report Django would mail for ``exc``."""
    return ExceptionReporter(None, type(exc), exc, exc.__traceback__).get_traceback_text()


def _raised() -> BaseException:
    """An exception raised and caught here, with its traceback."""
    try:
        raise RuntimeError("something broke")
    except RuntimeError:
        return sys.exc_info()[1] or RuntimeError()


def test_the_settings_in_a_report_hide_the_bounce_mailbox_password(settings: Settings) -> None:
    """``BOUNCE_IMAP_URL`` is listed with its password masked."""
    settings.BOUNCE_IMAP_URL = FAKE_BOUNCE_IMAP_URL

    assert PASSWORD not in _report(_raised())


def test_the_settings_in_a_report_keep_the_mailbox_host(settings: Settings) -> None:
    """Only the password is masked: the host is still there to debug with."""
    settings.BOUNCE_IMAP_URL = FAKE_BOUNCE_IMAP_URL

    assert "@imap.example.org/Bounces" in _report(_raised())


@pytest.mark.parametrize(
    "value",
    [
        "postgres://caldart:dbsecret@localhost:5432/caldart",
        "smtp+tls://ops%40example.org:dbsecret@smtp.example.org:587",
        {"OPTIONS": ["imaps://u:dbsecret@h/INBOX"]},
    ],
    ids=["database-url", "email-url", "nested"],
)
def test_any_url_with_a_password_is_masked(value: object) -> None:
    """A URL's password is masked under any setting name, nested ones included."""
    cleansed = CredentialSafeExceptionReporterFilter().cleanse_setting("ANY_URL", value)

    assert "dbsecret" not in repr(cleansed)


def test_a_url_without_a_password_is_left_alone() -> None:
    """``SITE_URL`` and the like read as they are."""
    cleansed = CredentialSafeExceptionReporterFilter().cleanse_setting(
        "SITE_URL", "https://caldart.example.org/portal"
    )

    assert cleansed == "https://caldart.example.org/portal"


def test_a_failed_bounce_check_reports_no_password(fake_mailbox: FakeMailbox) -> None:
    """The traceback of a failed check shows none of its frames' secrets."""
    fake_mailbox(refuse=ConnectionRefusedError(111, "Connection refused"))

    with pytest.raises(BounceCheckError) as raised:
        check_bounces()

    assert PASSWORD not in _report(raised.value)


def test_the_mailbox_address_never_prints_its_password() -> None:
    """The parsed address's ``repr`` leaves the password out."""
    assert PASSWORD not in repr(parse_imap_url(FAKE_BOUNCE_IMAP_URL))
