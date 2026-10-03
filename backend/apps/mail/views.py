"""The unsubscribe page a bulk email's link opens, in the public site's shell.

``GET /mail/unsubscribe/<token>`` shows the type the link turns off and one
**Unsubscribe** button, and records nothing: a mail scanner that follows every link in
a message must not unsubscribe anybody.  ``POST`` to the same address records the
opt-out, from the button or straight from a mail program's own one-click unsubscribe
(RFC 8058), and answers 200 with a page saying so.  A token that does not read is a
400 page in both cases.
"""

from __future__ import annotations

import logging

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.mail.models import OptOutSource
from apps.mail.types import is_opted_out, set_opt_out
from apps.mail.unsubscribe import UnsubscribeLinkError, read_token

log = logging.getLogger(__name__)

#: The page every state of the unsubscribe link renders.
TEMPLATE = "mail/unsubscribe.html"


# A one-click unsubscribe is a POST a mail provider sends on the recipient's behalf,
# with no session and no CSRF token to send; the signed token in the address is what
# authorizes it, so the CSRF check would refuse exactly the request this view exists
# to accept.
@csrf_exempt
@require_http_methods(["GET", "POST"])
def unsubscribe(request: HttpRequest, token: str) -> HttpResponse:
    """Show, or record, the opt-out the signed ``token`` names.

    The page's ``state`` is ``confirm`` on a GET (the type's name and an
    **Unsubscribe** button posting back here), ``already`` on a GET when the person has
    turned the type off already, ``done`` once a POST has recorded the opt-out with the
    source ``unsubscribe`` (or found it recorded), and ``not_allowed`` on either
    method for a type that no longer allows opting out, which records nothing.  A
    tampered, expired, or orphaned token renders ``expired`` with status 400 and
    records nothing.  Every state but ``expired`` answers 200.
    """
    try:
        user, email_type = read_token(token)
    except UnsubscribeLinkError as error:
        log.info("Refused an unsubscribe link: %s", error)
        return render(request, TEMPLATE, {"state": "expired"}, status=400)

    context: dict[str, object] = {"email_type": email_type}
    if not email_type.allow_opt_out:
        return render(request, TEMPLATE, {**context, "state": "not_allowed"})
    if request.method == "POST":
        set_opt_out(user, email_type, opted_out=True, source=OptOutSource.UNSUBSCRIBE, actor=user)
        return render(request, TEMPLATE, {**context, "state": "done"})
    state = "already" if is_opted_out(user, email_type) else "confirm"
    return render(request, TEMPLATE, {**context, "state": state})
