"""What every bulk email view shares: finding the email, and answering a refusal.

Every endpoint is CalDART management's (``management``) and a DART leader's
(``dart_leader``); a system administrator passes as for every role.  An anonymous caller
is a 401, from ``caldart.exceptions``.  A caller reaches only the bulk emails
``apps.bulk_email.drafts.visible_to`` gives them, every one for CalDART management and
their own for a DART leader, and any other id is a 404.  A DART leader also reads,
through :func:`readable_email_for`, another sender's email to their own DART.
"""

from __future__ import annotations

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import IsBulkSender
from apps.bulk_email.drafts import visible_to
from apps.bulk_email.models import BulkEmail
from apps.bulk_email.senders import readable_by
from apps.members.api.actors import acting_user
from caldart.exceptions import DomainError

#: The permission every bulk email endpoint carries.
BULK_EMAIL_PERMISSIONS = [IsBulkSender]


def email_for(request: Request, pk: int) -> BulkEmail:
    """The bulk email ``pk`` the caller may open; ``Http404`` for any other."""
    return get_object_or_404(visible_to(acting_user(request)), pk=pk)


def readable_email_for(request: Request, pk: int) -> BulkEmail:
    """The bulk email ``pk`` the caller may read; ``Http404`` for any other.

    That is :func:`email_for`'s, and for a DART leader also another sender's email to
    their own DART once it has started (``apps.bulk_email.senders.readable_by``).
    """
    return get_object_or_404(readable_by(acting_user(request)), pk=pk)


def stoppable_email_for(request: Request, pk: int) -> BulkEmail:
    """The bulk email ``pk`` the caller may **Stop**; ``Http404`` for any other.

    The caller's own and, for a mission callout, any they may read, so a co-leader of the
    callout's DART can stop a round of reminders they started.
    """
    bulk = readable_email_for(request, pk)
    if bulk.is_callout or visible_to(acting_user(request)).filter(pk=bulk.pk).exists():
        return bulk
    raise Http404


def refused(error: DomainError) -> Response:
    """409 ``{"detail": <sentence>}``: an action the email's state does not allow."""
    return Response({"detail": error.message}, status=status.HTTP_409_CONFLICT)
