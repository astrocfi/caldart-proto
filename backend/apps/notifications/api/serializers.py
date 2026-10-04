"""Serializers for the notification endpoints."""

from __future__ import annotations

from typing import Any, TypedDict

from django.db import IntegrityError, transaction
from rest_framework import serializers

from apps.accounts.models import User
from apps.notifications.events import EVENTS
from apps.notifications.models import NotificationSubscription
from apps.notifications.services import refresh_recipient, refused_event
from caldart.messages import email_messages

#: What a subscription with no event is refused with.
NO_EVENTS_MESSAGE = "Choose at least one event."

#: What a slug the catalog does not list is refused with.
UNKNOWN_EVENT_MESSAGE = "Unknown event '{slug}'."

#: What an event the bound account's roles do not admit is refused with.
NOT_PERMITTED_MESSAGE = "{name} does not hold a role that may receive {label}."

#: What a subscription to an address no account holds is refused with until confirmed.
CONFIRM_MESSAGE = "Check the box to confirm this address may receive these notifications."

#: What a second subscription for one address is refused with.
TAKEN_MESSAGE = "This address already has a subscription."


class NotificationEventDict(TypedDict):
    """One event as ``GET /notifications/events`` describes it."""

    slug: str
    label: str
    category: str
    description: str
    roles: list[str]


class NotificationEventSerializer(serializers.Serializer[NotificationEventDict]):
    """One entry of ``GET /notifications/events``: an event an address may subscribe to.

    ``slug`` names it in a subscription's ``events``, ``label`` is the words the screen
    and the email log use, ``category`` the heading it is listed under, ``description``
    one sentence saying when it happens, and ``roles`` the role slugs whose holders may
    receive it (a system administrator and a superuser always may).
    """

    slug = serializers.CharField()
    # DRF's Field.label is a different thing from this serializer's own `label`
    # field, so the stubs see the declaration as a narrowing of the attribute.
    label = serializers.CharField()  # type: ignore[assignment]
    category = serializers.CharField()
    description = serializers.CharField()
    roles = serializers.ListField(child=serializers.CharField())


def checked_events(slugs: list[str]) -> list[str]:
    """``slugs`` once each, in catalog order, once the catalog lists every one of them.

    An empty list raises ``ValidationError`` reading :data:`NO_EVENTS_MESSAGE`; a slug
    the catalog does not list raises it reading :data:`UNKNOWN_EVENT_MESSAGE`, naming
    the first such slug.
    """
    if len(slugs) == 0:
        raise serializers.ValidationError(NO_EVENTS_MESSAGE)
    unknown = next((slug for slug in slugs if slug not in EVENTS), None)
    if unknown is not None:
        raise serializers.ValidationError(UNKNOWN_EVENT_MESSAGE.format(slug=unknown))
    chosen = set(slugs)
    return [slug for slug in EVENTS if slug in chosen]


def check_permitted(user: User, slugs: list[str]) -> None:
    """Refuse ``slugs`` under ``events`` unless ``user``'s roles admit every one of them.

    The refusal reads :data:`NOT_PERMITTED_MESSAGE`, naming the account and the label
    of the first refused event in the order ``slugs`` gives.
    """
    refused = refused_event(user, slugs)
    if refused is None:
        return
    message = NOT_PERMITTED_MESSAGE.format(name=user.display_name, label=EVENTS[refused].label)
    raise serializers.ValidationError({"events": [message]})


def _address_taken(subscription: NotificationSubscription) -> bool:
    """Whether another subscription already holds ``subscription``'s address."""
    others = NotificationSubscription.objects.exclude(pk=subscription.pk)
    return others.filter(recipient_email__iexact=subscription.recipient_email).exists()


class NotificationSubscriptionSerializer(serializers.ModelSerializer[NotificationSubscription]):
    """One subscription, as ``/notifications/subscriptions`` answers and edits it.

    ``recipient_name`` is the bound account's name (blank for an address outside
    CalDART), and ``created_by_name`` who set it up (blank once that account is gone).
    A ``PATCH`` may change ``events`` and ``is_active``; every other field is
    read-only.  The events are checked as :func:`checked_events` checks them.  The
    recipient is brought up to date first, so a bare address an account has since
    taken is bound to it.  For a bound account, adding an event its roles do not admit
    is refused, and so is resuming a paused subscription that lists one; both under
    ``events`` with :data:`NOT_PERMITTED_MESSAGE`.
    """

    recipient_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    events = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = NotificationSubscription
        fields = [
            "id",
            "recipient_user",
            "recipient_name",
            "recipient_email",
            "events",
            "is_active",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "recipient_user",
            "recipient_email",
            "created_at",
            "updated_at",
        ]

    def get_recipient_name(self, subscription: NotificationSubscription) -> str:
        """The bound account's name, or blank for an address outside CalDART."""
        user = subscription.recipient_user
        return user.display_name if user is not None else ""

    def get_created_by_name(self, subscription: NotificationSubscription) -> str:
        """The name of the account that set the subscription up, or blank."""
        creator = subscription.created_by
        return creator.display_name if creator is not None else ""

    def validate_events(self, value: list[str]) -> list[str]:
        """The events once each, in catalog order, once the catalog lists every one."""
        return checked_events(value)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Check the edit against the roles of the account the subscription is bound to.

        Only the events the edit adds are checked, so dropping events from an account
        that has since lost a role still works; resuming checks every event listed.
        """
        instance = self.instance
        assert isinstance(instance, NotificationSubscription)  # noqa: S101 - PATCH has one
        if refresh_recipient(instance) and _address_taken(instance):
            instance.refresh_from_db(fields=["recipient_user", "recipient_email"])
        user = instance.recipient_user
        if user is None:
            return attrs
        events: list[str] = attrs.get("events", instance.events)
        resuming = attrs.get("is_active") is True and not instance.is_active
        if resuming:
            check_permitted(user, events)
        elif "events" in attrs:
            check_permitted(user, [slug for slug in events if slug not in instance.events])
        return attrs


class NotificationSubscriptionCreateSerializer(
    serializers.ModelSerializer[NotificationSubscription]
):
    """``POST /notifications/subscriptions``: an address and the events it hears about.

    ``recipient_email`` is the address and ``events`` the event slugs, checked as
    :func:`checked_events` checks them.  An address that already has a subscription
    (compared without regard to case) is refused under ``recipient_email`` with
    :data:`TAKEN_MESSAGE`.  When an account holds the address (compared the same way),
    the subscription is bound to it and takes the account's own address, and every
    event must be one the account's roles admit (:func:`check_permitted`).  When no
    account holds it, ``confirmed`` must be true or the address is refused under
    ``confirmed`` with :data:`CONFIRM_MESSAGE`.  The caller sets the subscription up,
    and it starts active.
    """

    events = serializers.ListField(child=serializers.CharField())
    confirmed = serializers.BooleanField(default=False, write_only=True)
    # Declared rather than generated, so the model's unique check does not answer
    # first with Django's own wording and case-sensitive comparison.
    recipient_email = serializers.EmailField(
        error_messages=email_messages("Enter the address to email.")
    )

    class Meta:
        model = NotificationSubscription
        fields = ["recipient_email", "events", "confirmed"]

    def validate_recipient_email(self, value: str) -> str:
        """The address, stripped, once no subscription holds it already."""
        address = value.strip()
        if NotificationSubscription.objects.filter(recipient_email__iexact=address).exists():
            raise serializers.ValidationError(TAKEN_MESSAGE)
        return address

    def validate_events(self, value: list[str]) -> list[str]:
        """The events once each, in catalog order, once the catalog lists every one."""
        return checked_events(value)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Bind the address to the account that holds it, or require the confirmation."""
        confirmed = attrs.pop("confirmed")
        user = User.objects.filter(email__iexact=attrs["recipient_email"]).first()
        if user is None:
            if not confirmed:
                raise serializers.ValidationError({"confirmed": [CONFIRM_MESSAGE]})
            return attrs
        check_permitted(user, attrs["events"])
        return {**attrs, "recipient_user": user, "recipient_email": user.email}

    def create(self, validated_data: dict[str, Any]) -> NotificationSubscription:
        """Save it, set up by the ``creator`` context entry.

        An address another request subscribed after this one was checked is refused
        under ``recipient_email`` with :data:`TAKEN_MESSAGE`, as the check refuses it.
        """
        try:
            with transaction.atomic():
                return NotificationSubscription.objects.create(
                    **validated_data, created_by=self.context["creator"]
                )
        except IntegrityError as exc:
            raise serializers.ValidationError({"recipient_email": [TAKEN_MESSAGE]}) from exc
