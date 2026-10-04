"""The answer page a mission callout's buttons open, in the public site's shell.

``GET /mail/callout/<token>`` shows the callout's subject and message as the person's
copy had it, the three answers (the one ``?answer=`` names chosen, else the person's
current answer), a note field, and **Send answer**, and records nothing: a mail scanner
that follows every link in a message must not answer for anybody.  ``POST`` to the same
address records the answer (``apps.bulk_email.callouts.record_answer``) and shows it.
Once the callout has closed both say so and record nothing, and so does a link whose
account has since been deactivated.  A token that does not read is a 400 page.  Each link
may send at most ``CALLOUT_ANSWER_THROTTLE_RATE`` answers
(``apps.bulk_email.throttling.CalloutAnswerThrottle``).
"""

from __future__ import annotations

import logging

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.bulk_email.callout_links import ANSWER_ORDER, CalloutLinkError, at_words, read_token
from apps.bulk_email.callouts import (
    NOTE_MAX_LENGTH,
    AnswerPage,
    answer_page,
    closed_moment,
    record_answer,
)
from apps.bulk_email.models import CalloutAnswerKind
from apps.bulk_email.throttling import CalloutAnswerThrottle
from caldart.exceptions import DomainError

log = logging.getLogger(__name__)

#: The page every state of the answer link renders.
TEMPLATE = "bulk_email/callout.html"

#: What the page says when **Send answer** is pressed with no answer chosen.
CHOOSE_MESSAGE = "Choose one of the three answers."

#: The status of a page refused because the link has sent too many answers.
TOO_MANY_STATUS = 429


# The answer page is opened from a link in an email, often in a mail program's own
# browser with no session cookie; the signed token in the address is what authorizes
# the answer, and nothing the session could vouch for is changed, so the CSRF check
# would refuse exactly the people the page exists for.
@csrf_exempt
@require_http_methods(["GET", "POST"])
def callout_answer(request: HttpRequest, token: str) -> HttpResponse:
    """Show, or record, the signed ``token``'s person's answer to its callout.

    The page's ``state`` is ``form`` on a GET while the callout takes answers, with the
    answer ``?answer=`` names chosen when it is one of the kinds, else the person's
    current one; ``done`` once a POST has recorded the answer; and ``closed`` on either
    method once the callout has closed, which records nothing; ``inactive`` on either
    method for an account since deactivated, saying the link no longer works, which
    records nothing.  A POST with no answer, or one that is not a kind, shows ``form``
    again with :data:`CHOOSE_MESSAGE` and status 400.  A POST past the link's limit of
    answers renders ``busy`` with status 429 and records nothing.  A tampered token, or
    one naming a callout or account since deleted, renders ``invalid`` with status 400
    and records nothing.
    """
    try:
        callout, user = read_token(token)
    except CalloutLinkError as error:
        log.info("Refused a callout link: %s", error)
        return render(request, TEMPLATE, {"state": "invalid"}, status=400)

    if not user.is_active:
        return render(request, TEMPLATE, {"state": "inactive"})
    page = answer_page(callout, user)
    if not page.is_open:
        return _render(request, page, state="closed")
    if request.method == "GET":
        chosen = request.GET.get("answer", "")
        if chosen not in CalloutAnswerKind.values:
            chosen = "" if page.answer is None else page.answer.answer
        note = "" if page.answer is None else page.answer.note
        return _render(request, page, state="form", chosen=chosen, note=note)

    if not CalloutAnswerThrottle(token).allows(request):
        return _render(request, page, state="busy", status=TOO_MANY_STATUS)
    chosen = request.POST.get("answer", "")
    note = request.POST.get("note", "")
    if chosen not in CalloutAnswerKind.values:
        return _render(request, page, state="form", note=note, error=CHOOSE_MESSAGE, status=400)
    try:
        record_answer(callout, user, answer=chosen, note=note)
    except DomainError:
        # The callout closed between the read above and the answer.
        return _render(request, answer_page(callout, user), state="closed")
    return _render(request, answer_page(callout, user), state="done")


def _render(
    request: HttpRequest,
    page: AnswerPage,
    *,
    state: str,
    chosen: str = "",
    note: str = "",
    error: str = "",
    status: int = 200,
) -> HttpResponse:
    """The answer page for ``page`` in ``state``, with the form's values when it shows."""
    choices = [(kind, CalloutAnswerKind(kind).label) for kind in ANSWER_ORDER]
    answer = page.answer
    context: dict[str, object] = {
        "state": state,
        "page": page,
        "choices": choices,
        "chosen": chosen,
        "note": note,
        "note_max_length": NOTE_MAX_LENGTH,
        "error": error,
        "closes": at_words(closed_moment(page.callout)),
        "answer_label": "" if answer is None else CalloutAnswerKind(answer.answer).label,
        "answered": "" if answer is None else at_words(answer.answered_at),
    }
    return render(request, TEMPLATE, context, status=status)
