"""System checks for the mail settings.

:func:`check_bounce_address` refuses a ``BOUNCE_ADDRESS`` the signed bounce address
cannot be made from; ``apps.mail.apps.MailConfig.ready`` registers it, so ``manage.py
check`` and every command that runs the checks report it.
"""

from __future__ import annotations

from collections.abc import Sequence
from email.utils import parseaddr
from typing import Any

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import CheckMessage, Error

from caldart.mail import BOUNCE_LOCAL_PART_MAX_LENGTH

#: The check id of a ``BOUNCE_ADDRESS`` that is not a bare ``local@domain`` address.
NOT_BARE_ID = "mail.E001"

#: The check id of a ``BOUNCE_ADDRESS`` whose local part leaves no room for the tag.
LOCAL_PART_TOO_LONG_ID = "mail.E002"


def check_bounce_address(
    app_configs: Sequence[AppConfig] | None = None, **kwargs: Any
) -> list[CheckMessage]:
    """Errors for a ``BOUNCE_ADDRESS`` the signed bounce address cannot be made from.

    An empty setting is fine and answers ``[]``: bounce checking is simply off.
    Otherwise the setting must be a bare address, ``local@domain`` with no display name,
    angle brackets, or spaces, else :data:`NOT_BARE_ID`; and its local part may have at
    most ``caldart.mail.BOUNCE_LOCAL_PART_MAX_LENGTH`` (28) characters, so the signed
    form fits an address's 64, else :data:`LOCAL_PART_TOO_LONG_ID`.
    """
    configured: str = settings.BOUNCE_ADDRESS
    if configured == "":
        return []
    local, at, domain = configured.rpartition("@")
    is_bare = parseaddr(configured)[1] == configured and not any(c.isspace() for c in configured)
    if not is_bare or at == "" or local == "" or domain == "":
        return [
            Error(
                "BOUNCE_ADDRESS must be a bare address, local@domain, with no display name.",
                hint="Write it as bounces@caldart.example.org.",
                id=NOT_BARE_ID,
            )
        ]
    if len(local) > BOUNCE_LOCAL_PART_MAX_LENGTH:
        return [
            Error(
                f"BOUNCE_ADDRESS's local part is {len(local)} characters; at most "
                f"{BOUNCE_LOCAL_PART_MAX_LENGTH} leave room for the signed tag.",
                hint="Use a short local part, such as bounces.",
                id=LOCAL_PART_TOO_LONG_ID,
            )
        ]
    return []
