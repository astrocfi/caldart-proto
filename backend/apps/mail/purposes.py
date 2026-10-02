"""What each email the installation sends is for, in words a reader understands.

An email log row records its ``purpose`` as the template the body came from --
``reminder_second``, ``receipt``, ``password_reset`` -- which is exact but not
readable.  :func:`purpose_labels` is the one place those names become words: the
email log's rows carry the label, the report prints it, and the portal's purpose
filter offers the labels in this order.  The renewal reminders come first, labeled
from the stored reminder schedule so their days are the ones the scanner uses;
:data:`PURPOSE_LABELS` holds every other purpose.
"""

from __future__ import annotations

#: The label of every email template but the renewal reminders', in the order the
#: purpose filter offers them after the reminders.
PURPOSE_LABELS: dict[str, str] = {
    "renewal_enabled": "Renewal turned on",
    "renewal_notice": "Renewal notice",
    "renewal_card_expiring": "Card expiring",
    "renewal_charged": "Renewal charged",
    "renewal_failed": "Renewal declined",
    "renewal_canceled": "Renewal turned off",
    "receipt": "Receipt",
    "refund": "Refund",
    "contribution_statement": "Contribution statement",
    "member_invitation": "Invitation",
    "password_reset": "Password reset",
    "email_verification": "Email verification",
    "scheduled_report": "Scheduled report",
    "dart_roster": "DART roster",
    # notifications: one per event, in the catalog's order.  The mail app sits below
    # the notifications app, so the labels are written out rather than read from it.
    "notification_signed_up": "Notification: Sign-up",
    "notification_member_added": "Notification: Member added by an administrator",
    "notification_became_friend": "Notification: Member became a friend",
    "notification_became_member": "Notification: Friend became a member",
    "notification_membership_paid": "Notification: Membership paid",
    "notification_membership_granted": "Notification: Membership granted by an administrator",
    "notification_membership_expired": "Notification: Membership expired",
    "notification_auto_renewal_on": "Notification: Automatic payment turned on",
    "notification_auto_renewal_off": "Notification: Automatic payment turned off",
    "notification_auto_renewal_declined": "Notification: Automatic payment declined",
    "notification_donation_received": "Notification: Donation received",
    "notification_payment_recorded": "Notification: Payment recorded by hand",
    "notification_payment_refunded": "Notification: Payment refunded",
    "notification_account_deactivated": "Notification: Account deactivated",
    "notification_account_reactivated": "Notification: Account reactivated",
    "notification_roles_changed": "Notification: Roles changed",
    "notification_email_changed": "Notification: Email address changed",
    "notification_profile_changed": "Notification: Profile changed",
    "notification_verification_changed": "Notification: Verification recorded",
    "notification_aircraft_added": "Notification: Aircraft added",
    "notification_aircraft_changed": "Notification: Aircraft changed",
    "notification_aircraft_removed": "Notification: Aircraft removed",
}


def purpose_labels() -> dict[str, str]:
    """Every purpose's label, in the order the purpose filter offers them.

    The five renewal reminders come first, worded from the stored reminder schedule
    (``"Renewal reminder (60 days)"`` on the default one), then
    :data:`PURPOSE_LABELS`.  Reads the schedule once, so a caller labeling many rows
    asks for the labels once and looks each row up with :func:`purpose_label`.
    """
    # Inline: reminders sits above mail in the app order, since it sends email, so
    # this module may not import it at the top.
    from apps.reminders.models import ReminderSchedule

    return {**ReminderSchedule.load().purpose_labels(), **PURPOSE_LABELS}


def purpose_label(purpose: str, labels: dict[str, str] | None = None) -> str:
    """The label of ``purpose`` in ``labels``, or ``purpose`` itself when none names it.

    ``labels`` defaults to :func:`purpose_labels`, read afresh.  The purposes are
    template names rather than a fixed enumeration, so a template added without a
    label still reads, by its own name, instead of vanishing.
    """
    if labels is None:
        labels = purpose_labels()
    return labels.get(purpose, purpose)
