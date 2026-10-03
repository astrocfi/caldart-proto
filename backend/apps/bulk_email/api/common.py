"""What every bulk email view shares: finding the email, and answering a refusal.

Every endpoint is CalDART management's (``management``); a system administrator passes
as for every role.  An anonymous caller is a 401, from ``caldart.exceptions``.  A caller
reaches only the bulk emails ``apps.bulk_email.drafts.visible_to`` gives them, and any
other id is a 404.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import IsManagement
from apps.bulk_email.drafts import visible_to
from apps.bulk_email.models import BulkEmail
from apps.members.api.actors import acting_user
from caldart.exceptions import DomainError

#: The permission every bulk email endpoint carries.
BULK_EMAIL_PERMISSIONS = [IsManagement]


def email_for(request: Request, pk: int) -> BulkEmail:
    """The bulk email ``pk`` the caller may open; ``Http404`` for any other."""
    return get_object_or_404(visible_to(acting_user(request)), pk=pk)


def refused(error: DomainError) -> Response:
    """409 ``{"detail": <sentence>}``: an action the email's state does not allow."""
    return Response({"detail": error.message}, status=status.HTTP_409_CONFLICT)
