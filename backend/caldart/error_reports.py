"""Error reports: what they may show of the settings, and a mailer that cannot fail.

Django's error reports (the mail ``AdminEmailHandler`` sends to ``ADMIN_EMAILS``, and
the debug page) list the settings, masking those whose name looks secret: ``KEY``,
``SECRET``, ``PASS``, ``TOKEN`` and the like.  A connection URL can carry a password
under a name that looks like nothing of the kind, ``BOUNCE_IMAP_URL`` for one, so
:class:`CredentialSafeExceptionReporterFilter` also masks the password part of every
URL in a setting's value, keeping the scheme, the user name and the host readable.
``DEFAULT_EXCEPTION_REPORTER_FILTER`` names it.

The error mail goes through the same mail server as everything else, so when that
server refuses a message it refuses the report too.  :class:`QuietAdminEmailHandler`
is the production ``mail_admins`` handler: a report it cannot send is written to
standard error, which the journal keeps, rather than raised into whatever logged it.
"""

from __future__ import annotations

import logging
import re

from django.utils.log import AdminEmailHandler
from django.views.debug import SafeExceptionReporterFilter

#: The ``password`` of a ``scheme://user:password@host`` URL anywhere in a string.
URL_PASSWORD = re.compile(r"(?P<head>[A-Za-z][A-Za-z0-9+.-]*://[^:@/\s]*:)[^@/\s]+(?=@)")


class CredentialSafeExceptionReporterFilter(SafeExceptionReporterFilter):
    """Django's reporter filter, also masking the password in any URL a setting holds."""

    def cleanse_setting(self, key: int | str, value: object) -> object:
        """``value`` cleansed as Django does, then with every URL's password masked.

        A dictionary or a list is walked by Django's own recursion, which calls back
        here for each item, so a URL nested in one is masked too.  Anything that is not
        a string passes through as Django left it.
        """
        cleansed = super().cleanse_setting(key, value)
        if isinstance(cleansed, str):
            return URL_PASSWORD.sub(rf"\g<head>{self.cleansed_substitute}", cleansed)
        return cleansed


class QuietAdminEmailHandler(AdminEmailHandler):
    """Django's ``AdminEmailHandler``, except that a report it cannot send never raises.

    With ``MAILERS`` configured, Django's handler sends the report without
    ``fail_silently``, so a refusing or unreachable mail server raises out of the
    ``log`` call that produced the report, failing a request that set out to survive
    the very same refusal.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Mail ``record`` to ``ADMINS``; on any failure, hand it to ``handleError``.

        ``handleError`` writes the failure's traceback to standard error and returns, so
        the caller that logged ``record`` carries on as if the mail had gone.
        """
        try:
            super().emit(record)
        # Broad on purpose: this is the ``logging.Handler`` contract every standard
        # handler follows, since a handler that raises fails the code that logged.
        except Exception:
            self.handleError(record)
