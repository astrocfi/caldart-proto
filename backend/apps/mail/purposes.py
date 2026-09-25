"""What each email the installation sends is for, in words a reader understands.

An email log row records its ``purpose`` as the template the body came from --
``reminder_t30``, ``receipt``, ``password_reset`` -- which is exact but not
readable.  :data:`PURPOSE_LABELS` is the one place those names become words: the
email log's rows carry the label, the report prints it, and the portal's purpose
filter offers the labels in this order.
"""

from __future__ import annotations

#: Every email template's label, in the order the purpose filter offers them.
PURPOSE_LABELS: dict[str, str] = {
    "reminder_t60": "Renewal reminder (60 days)",
    "reminder_t30": "Renewal reminder (30 days)",
    "reminder_t7": "Renewal reminder (7 days)",
    "reminder_expired": "Renewal reminder (expired)",
    "reminder_post30": "Renewal reminder (30 days after)",
    "renewal_enabled": "Renewal turned on",
    "renewal_notice": "Renewal notice",
    "renewal_card_expiring": "Card expiring",
    "renewal_charged": "Renewal charged",
    "renewal_failed": "Renewal declined",
    "renewal_canceled": "Renewal turned off",
    "receipt": "Receipt",
    "refund": "Refund",
    "member_invitation": "Invitation",
    "password_reset": "Password reset",
    "scheduled_report": "Scheduled report",
    "dart_roster": "DART roster",
}


def purpose_label(purpose: str) -> str:
    """The label of ``purpose``, or ``purpose`` itself when no label names it.

    The purposes are template names rather than a fixed enumeration, so a template
    added without a label still reads, by its own name, instead of vanishing.
    """
    return PURPOSE_LABELS.get(purpose, purpose)
