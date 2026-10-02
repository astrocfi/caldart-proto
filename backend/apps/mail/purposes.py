"""What each email the installation sends is for, in words a reader understands.

An email log row records its ``purpose`` as the template the body came from --
``reminder_second``, ``receipt``, ``password_reset`` -- which is exact but not
readable.  :func:`purpose_labels` is the one place those names become words: the
email log's rows carry the label, the report prints it, and the portal's purpose
filter offers the labels in this order.

:data:`PURPOSE_LABELS` holds the labels that never change.  An app above mail whose
labels depend on stored data registers a source of them with
:func:`register_purpose_labels` when it starts: the reminders app registers its five
reminder labels, worded from the stored reminder schedule, so they name the days the
scanner uses.  The mail app therefore never imports the apps that send through it.
"""

from __future__ import annotations

from collections.abc import Callable

#: A function answering labels by purpose, read afresh each time the labels are.
LabelSource = Callable[[], dict[str, str]]

#: The registered sources, in the order :func:`purpose_labels` merges them.
_label_sources: list[LabelSource] = []

#: The label of every email template whose label never changes, in the order the
#: purpose filter offers them after the registered sources' labels.
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
    "bulk_email": "Bulk email",
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


def register_purpose_labels(source: LabelSource) -> None:
    """Add ``source`` to the functions :func:`purpose_labels` reads labels from.

    Sources are merged in the order they were registered, ahead of
    :data:`PURPOSE_LABELS`.  Registering the same source twice registers it once.
    """
    if source not in _label_sources:
        _label_sources.append(source)


def purpose_labels() -> dict[str, str]:
    """Every purpose's label, in the order the purpose filter offers them.

    Each registered source's labels come first, read afresh in registration order --
    the five renewal reminders, worded from the stored reminder schedule
    (``"Renewal reminder (60 days)"`` on the default one) -- then
    :data:`PURPOSE_LABELS`.  A source may read the database, so a caller labeling
    many rows asks for the labels once and looks each row up with
    :func:`purpose_label`.
    """
    labels: dict[str, str] = {}
    for source in _label_sources:
        labels.update(source())
    return {**labels, **PURPOSE_LABELS}


def purpose_label(purpose: str, *, labels: dict[str, str] | None = None) -> str:
    """The label of ``purpose`` in ``labels``, or ``purpose`` itself when none names it.

    ``labels`` defaults to :func:`purpose_labels`, read afresh.  The purposes are
    template names rather than a fixed enumeration, so a template added without a
    label still reads, by its own name, instead of vanishing.
    """
    if labels is None:
        labels = purpose_labels()
    return labels.get(purpose, purpose)
