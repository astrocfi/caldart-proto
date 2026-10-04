"""The emails a mandate sends: their subjects, their shared context, and the send.

Every renewal email goes out through :func:`send_mandate_email`, which the mandate
services and the scan both call.
"""

from __future__ import annotations

import logging
import smtplib
from collections.abc import Sequence
from datetime import date
from typing import Any

from django.conf import settings

from apps.payments.models import MandateCadence, RenewalMandate
from apps.payments.renewals.schedule import (
    MandateKind,
    kind_label,
    mandate_kind,
    renewal_amount_cents,
)
from caldart.dates import format_display_date
from caldart.mail import Attachment, contact_email, error_name, org_name, send_templated
from caldart.reports import money_label

log = logging.getLogger(__name__)

#: How often each cadence charges, in running prose: "we will charge $25.00 each
#: month".
CADENCE_PHRASES: dict[str, str] = {
    MandateCadence.MONTHLY: "each month",
    MandateCadence.QUARTERLY: "each quarter",
    MandateCadence.YEARLY: "each year",
}

#: Subject lines, in the house voice: plain, specific, no exclamation marks.
#: Keyed by template and then by the mandate's kind, because a recurring donation
#: renews nothing and must never say it does.
SUBJECTS: dict[str, dict[str, str]] = {
    "renewal_enabled": {
        MandateKind.RENEWAL: "{org}: automatic renewal is on",
        MandateKind.BOTH: "{org}: automatic renewal is on",
        MandateKind.CONTRIBUTION: "{org}: your recurring donation is on",
    },
    "renewal_notice": {
        MandateKind.RENEWAL: "{org}: we will renew your membership on {charge_on}",
        MandateKind.BOTH: (
            "{org}: we will renew your membership and take your contribution on {charge_on}"
        ),
        MandateKind.CONTRIBUTION: "{org}: we will take your recurring donation on {charge_on}",
    },
    "renewal_card_expiring": {
        MandateKind.RENEWAL: "{org}: the card we renew your membership with expires soon",
        MandateKind.BOTH: "{org}: the card we renew your membership with expires soon",
        MandateKind.CONTRIBUTION: (
            "{org}: the card we take your recurring donation with expires soon"
        ),
    },
    "renewal_charged": {
        MandateKind.RENEWAL: "{org}: your membership has been renewed",
        MandateKind.BOTH: "{org}: your membership has been renewed",
        MandateKind.CONTRIBUTION: "{org}: thank you for your recurring donation",
    },
    "renewal_failed": {
        MandateKind.RENEWAL: "{org}: we could not renew your membership",
        MandateKind.BOTH: "{org}: we could not renew your membership",
        MandateKind.CONTRIBUTION: "{org}: we could not take your recurring donation",
    },
    "renewal_canceled": {
        MandateKind.RENEWAL: "{org}: automatic renewal is off",
        MandateKind.BOTH: "{org}: automatic renewal is off",
        MandateKind.CONTRIBUTION: "{org}: your recurring donation is off",
    },
}


def payments_url() -> str:
    """Absolute link to the portal's payments screen, which every email carries."""
    return f"{settings.SITE_URL.rstrip('/')}/portal/payments"


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------
def mandate_context(mandate: RenewalMandate, **extra: Any) -> dict[str, Any]:
    """The template context every renewal email shares, plus ``extra``.

    Carries the member's first name, the organization's name and contact
    address, the plan, the amount as the member reads it, the saved method's
    label and the link to the portal's payments screen.  ``kind`` is the
    mandate's :class:`MandateKind` and ``kind_label`` the words for it, which is
    how each template tells a renewal from a recurring donation.  ``plan_name`` is
    an empty string for a recurring donation, which names no plan, and
    ``cadence_label`` says how often the mandate charges ("each month").
    """
    amount_cents = renewal_amount_cents(mandate)
    kind = mandate_kind(mandate)
    context: dict[str, Any] = {
        "first_name": mandate.user.first_name or mandate.user.display_name,
        "org_name": org_name(),
        "contact_email": contact_email(),
        "kind": kind,
        "kind_label": kind_label(kind),
        "plan_name": mandate.plan.name if mandate.plan is not None else "",
        "amount": money_label(amount_cents),
        "amount_cents": amount_cents,
        "contribution": money_label(mandate.contribution_cents),
        "contribution_cents": mandate.contribution_cents,
        "cadence": mandate.cadence,
        "cadence_label": CADENCE_PHRASES[mandate.cadence],
        "method_label": mandate.method_label,
        "payments_url": payments_url(),
        "site_url": settings.SITE_URL.rstrip("/"),
    }
    context.update(extra)
    return context


def _subject_fields(extra: dict[str, Any]) -> dict[str, Any]:
    """``extra`` with every date written as a screen shows it, for a subject line."""
    return {
        key: format_display_date(value) if isinstance(value, date) else value
        for key, value in extra.items()
    }


def send_mandate_email(
    mandate: RenewalMandate,
    template: str,
    *,
    attachments: Sequence[Attachment] = (),
    **extra: Any,
) -> bool:
    """Send one renewal email to the mandate's member, and say whether it went.

    The subject comes from :data:`SUBJECTS` with the organization's name filled
    in and any date in ``extra`` written ``MM/DD/YYYY``, as the Sent emails page
    lists it; the body from ``emails/<template>.{txt,html}`` rendered over
    :func:`mandate_context`.  Each entry of ``attachments`` is a filename, its
    bytes and its media type, which is how the charge report carries the
    receipt.  A member with no email address is not written to.  The send is
    recorded in the email log under the template's name.

    A mail server that refuses the message is logged at ERROR and answered
    ``False`` rather than raised: one member's mail problem never stops a scan,
    and the timestamp that would have recorded the send stays unset.  The advance
    notice and the card-expiry warning are sent again on the next run because of
    that; the message that reports a charge or a decline is not resent, since the
    attempt it belongs to is already closed.
    """
    if not mandate.user.email:
        return False
    context = mandate_context(mandate, **extra)
    subject = SUBJECTS[template][context["kind"]].format(
        org=context["org_name"], **_subject_fields(extra)
    )
    try:
        send_templated(
            to=mandate.user.email,
            subject=subject,
            template=template,
            context=context,
            attachments=attachments,
            user_id=mandate.user_id,
        )
    except (smtplib.SMTPException, OSError) as exc:
        log.error(
            "renewal email failed: template=%s mandate=%s error=%s",
            template,
            mandate.pk,
            error_name(exc),
        )
        return False
    return True
