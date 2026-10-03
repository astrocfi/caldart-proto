"""Where a recipient's reply to a bulk email goes: the ``Reply-To`` every copy carries.

Every bulk email goes out ``From`` ``DEFAULT_FROM_EMAIL``, an address nobody reads, so
that SPF, DKIM, and DMARC align; a reply reaches a person only through ``Reply-To``.
``BulkEmail.reply_to`` is the address the sender chose, and blank means the default:
``BULK_EMAIL_REPLY_TO``, or the sender's own address when that setting is blank.
:func:`default_reply_to` answers the default for a sender, :func:`reply_to_for` the
address an email's copies carry, :func:`reply_to_problem` why an address cannot be
used, and :func:`claimed_reply_to` the address the background sender settles on as it
starts a send.
"""

from __future__ import annotations

import logging
from email.utils import parseaddr

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.accounts.models import User
from apps.bulk_email.models import BulkEmail

log = logging.getLogger(__name__)

log = logging.getLogger(__name__)

#: Why a ``Reply-To`` address is refused; ``{address}`` is the address as written.
INVALID_MESSAGE = (
    "Replies would go to {address}, which is not a valid email address. Change the "
    "Reply-To address under What it says."
)

#: Why an email with no ``Reply-To`` address at all is refused.
MISSING_MESSAGE = (
    "There is no address for replies to go to. Write one in Reply-To under What it says."
)


def default_reply_to(sender: User | None) -> str:
    """The address replies go to when the sender chooses none.

    That is ``BULK_EMAIL_REPLY_TO``, trimmed, or, when the setting is blank,
    ``sender``'s own address; ``""`` when both are blank or the sender's account is
    gone.
    """
    configured = str(settings.BULK_EMAIL_REPLY_TO).strip()
    if configured != "":
        return configured
    return sender.email if sender is not None else ""


def reply_to_for(bulk: BulkEmail) -> str:
    """The ``Reply-To`` address ``bulk``'s copies carry.

    ``bulk.reply_to`` when the sender chose one, otherwise :func:`default_reply_to`
    for its sender.
    """
    if bulk.reply_to != "":
        return bulk.reply_to
    return default_reply_to(bulk.sender)


def reply_to_problem(address: str) -> str | None:
    """Why ``address`` cannot be a ``Reply-To`` address, or ``None`` when it can.

    A blank address is refused with :data:`MISSING_MESSAGE`, and one Django's
    ``validate_email`` refuses with :data:`INVALID_MESSAGE` naming it.
    """
    if address == "":
        return MISSING_MESSAGE
    try:
        validate_email(address)
    except ValidationError:
        return INVALID_MESSAGE.format(address=address)
    return None


def claimed_reply_to(bulk: BulkEmail) -> str:
    """The ``Reply-To`` the background sender sends ``bulk``'s copies with.

    It is :func:`reply_to_for`, resolved and checked again as the send starts: a queued
    email can still be changed, its default with it, and its sender's account can be
    deleted.  When that address is blank or not valid the copies fall back to the
    address of ``DEFAULT_FROM_EMAIL``, and a WARNING on this module's logger names the
    email by id.
    """
    address = reply_to_for(bulk)
    if reply_to_problem(address) is None:
        return address
    log.warning("bulk email %s has no usable Reply-To; replies go to DEFAULT_FROM_EMAIL", bulk.pk)
    return parseaddr(str(settings.DEFAULT_FROM_EMAIL))[1]
