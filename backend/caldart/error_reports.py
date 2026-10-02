"""What an error report may show of the settings: no password, wherever it sits.

Django's error reports (the mail ``AdminEmailHandler`` sends to ``ADMIN_EMAILS``, and
the debug page) list the settings, masking those whose name looks secret: ``KEY``,
``SECRET``, ``PASS``, ``TOKEN`` and the like.  A connection URL can carry a password
under a name that looks like nothing of the kind, ``BOUNCE_IMAP_URL`` for one, so
:class:`CredentialSafeExceptionReporterFilter` also masks the password part of every
URL in a setting's value, keeping the scheme, the user name and the host readable.
``DEFAULT_EXCEPTION_REPORTER_FILTER`` names it.
"""

from __future__ import annotations

import re

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
