"""Serializers for the report endpoints."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.darts.models import Dart
from apps.reports.models import ReportSubscription, SavedColumnSet
from apps.reports.registry import REPORTS
from apps.reports.schedule import next_due_after
from apps.reports.services import recipient_may_read
from caldart.reports import FIXED_COLUMNS_MESSAGE, Report, select_columns
from caldart.runs import RunActionSerializer

#: What a saved set with no columns is refused with.
NO_COLUMNS_MESSAGE = "Choose at least one column."

#: What a subscription for an account that may not read its report is refused with.
NOT_PERMITTED_MESSAGE = "{name} does not hold a role that may read this report."

#: What a subscription to an address no account holds is refused with until confirmed.
CONFIRM_MESSAGE = "Tick the box to confirm this address may receive this report."

#: What a ``columns`` entry among a subscription's filters is refused with.
COLUMNS_AS_FILTER_MESSAGE = "Choose columns with the columns field, not as a filter."


class ReportSummaryDict(TypedDict):
    """One report as ``GET /reports`` describes it."""

    slug: str
    title: str
    choosable: bool
    periods: bool


class ReportSummarySerializer(serializers.Serializer[ReportSummaryDict]):
    """One entry of ``GET /reports``: a report the caller may read.

    ``slug`` names it in every report URL, ``title`` labels it, ``choosable`` says
    whether ``?columns=`` may choose its columns, and ``periods`` whether it takes
    ``?period=``.
    """

    slug = serializers.CharField()
    title = serializers.CharField()
    choosable = serializers.BooleanField()
    periods = serializers.BooleanField()


def checked_columns(spec: Report, keys: Sequence[str]) -> list[str]:
    """``keys`` as a list, once ``spec``'s registry accepts them.

    An empty list is the report's default columns and always passes.  Any key at all
    for a report whose columns are fixed raises ``ValidationError`` reading
    :data:`~caldart.reports.FIXED_COLUMNS_MESSAGE`; an unknown or repeated key raises
    it with the message :func:`~caldart.reports.select_columns` gives, naming the key.
    """
    if len(keys) == 0:
        return []
    if not spec.choosable:
        raise serializers.ValidationError(FIXED_COLUMNS_MESSAGE)
    try:
        select_columns(spec.columns, keys)
    except ValueError as exc:
        raise serializers.ValidationError(str(exc)) from exc
    return list(keys)


class SavedColumnSetSerializer(serializers.ModelSerializer[SavedColumnSet]):
    """One saved set of a report's columns: ``{id, name, columns}``.

    Written with ``name`` (1 to 60 characters) and ``columns`` (the keys, in the order
    the report prints them).  The report is the one in the URL, handed in as the
    ``spec`` context entry; its registry must hold every key, no key may repeat, at
    least one is needed, and a report whose columns are fixed keeps no sets.
    """

    columns = serializers.ListField(child=serializers.CharField())

    class Meta:
        model = SavedColumnSet
        fields = ["id", "name", "columns"]
        read_only_fields = ["id"]

    def validate_columns(self, value: list[str]) -> list[str]:
        """The keys, once the report in the ``spec`` context entry accepts them."""
        spec: Report = self.context["spec"]
        if not spec.choosable:
            raise serializers.ValidationError(FIXED_COLUMNS_MESSAGE)
        if len(value) == 0:
            raise serializers.ValidationError(NO_COLUMNS_MESSAGE)
        return checked_columns(spec, value)


def checked_contents(spec: Report, filters: Mapping[str, str], columns: Sequence[str]) -> None:
    """Refuse ``filters`` and ``columns`` unless ``spec`` builds a report from them today.

    The columns go through :func:`checked_columns`, and then the report is built exactly
    as a download builds it, so a filter value the report's list refuses is refused
    here too.  Errors are keyed as the subscription's fields are: ``columns`` for the
    columns, and ``filters`` holding the report's own errors keyed by filter.  A
    ``columns`` entry among the filters is refused with
    :data:`COLUMNS_AS_FILTER_MESSAGE`.
    """
    try:
        chosen = checked_columns(spec, columns)
    except serializers.ValidationError as exc:
        raise serializers.ValidationError({"columns": exc.detail}) from exc
    if "columns" in filters:
        raise serializers.ValidationError({"filters": {"columns": [COLUMNS_AS_FILTER_MESSAGE]}})
    params = {**filters, "columns": ",".join(chosen)} if chosen else dict(filters)
    try:
        spec.table(params, fmt="csv", today=timezone.localdate())
    except serializers.ValidationError as exc:
        raise serializers.ValidationError({"filters": exc.detail}) from exc


def not_permitted(user: User) -> str:
    """The refusal naming ``user``, an account that may not read the report."""
    return NOT_PERMITTED_MESSAGE.format(name=user.display_name)


class ReportSubscriptionSerializer(serializers.ModelSerializer[ReportSubscription]):
    """One report subscription, as ``/reports/subscriptions`` answers and edits it.

    ``report_title`` labels the report, ``recipient_name`` is the bound account's name
    (blank for an address outside CalDART), and ``created_by_name`` who set it up
    (blank once that account is gone).  A ``PATCH`` may change ``is_active``,
    ``filters``, ``columns``, ``formats``, ``cadence`` and ``weekday``; every other
    field is read-only.  The filters and columns are checked against the report on
    every write (:func:`checked_contents`), and resuming a subscription whose account
    may no longer read the report is refused under ``is_active``.  Changing the
    cadence or the weekday moves ``next_due_on`` to the schedule's next day after
    today.
    """

    report_title = serializers.SerializerMethodField()
    recipient_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    filters = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False)
    columns = serializers.ListField(child=serializers.CharField(), required=False)
    weekday = serializers.IntegerField(min_value=0, max_value=6, required=False)

    class Meta:
        model = ReportSubscription
        fields = [
            "id",
            "report",
            "report_title",
            "recipient_user",
            "recipient_name",
            "recipient_email",
            "filters",
            "columns",
            "formats",
            "cadence",
            "weekday",
            "is_active",
            "created_by_name",
            "last_sent_at",
            "next_due_on",
        ]
        read_only_fields = [
            "id",
            "report",
            "recipient_user",
            "recipient_email",
            "last_sent_at",
            "next_due_on",
        ]

    def get_report_title(self, subscription: ReportSubscription) -> str:
        """The title of the report the subscription sends."""
        return REPORTS[subscription.report].title

    def get_recipient_name(self, subscription: ReportSubscription) -> str:
        """The bound account's name, or blank for an address outside CalDART."""
        user = subscription.recipient_user
        return user.display_name if user is not None else ""

    def get_created_by_name(self, subscription: ReportSubscription) -> str:
        """The name of the account that set the subscription up, or blank."""
        creator = subscription.created_by
        return creator.display_name if creator is not None else ""

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Check the edit against the subscription's report and its recipient.

        The filters and columns are checked only when the edit changes one of them, so
        a subscription whose stored filters no longer build can still be paused.
        """
        instance = self.instance
        assert isinstance(instance, ReportSubscription)  # noqa: S101 - PATCH has an instance
        spec = REPORTS[instance.report]
        if "filters" in attrs or "columns" in attrs:
            checked_contents(
                spec,
                attrs.get("filters", instance.filters),
                attrs.get("columns", instance.columns),
            )
        user = instance.recipient_user
        resuming = attrs.get("is_active") is True
        if resuming and user is not None and not recipient_may_read(instance, spec):
            raise serializers.ValidationError({"is_active": [not_permitted(user)]})
        return attrs

    def update(
        self, instance: ReportSubscription, validated_data: dict[str, Any]
    ) -> ReportSubscription:
        """Save the edit, moving ``next_due_on`` when the schedule changed."""
        cadence = validated_data.get("cadence", instance.cadence)
        weekday = validated_data.get("weekday", instance.weekday)
        if (cadence, weekday) != (instance.cadence, instance.weekday):
            validated_data["next_due_on"] = next_due_after(cadence, weekday, timezone.localdate())
        return super().update(instance, validated_data)


class ReportSubscriptionCreateSerializer(serializers.ModelSerializer[ReportSubscription]):
    """``POST /reports/subscriptions``: a report, its recipient and its schedule.

    ``report`` is a registered slug and ``recipient_email`` the address.  When an
    account holds that address (compared without regard to case), the subscription is
    bound to it and takes the account's own address, and an account that may not read
    the report is refused under ``recipient_email`` with :data:`NOT_PERMITTED_MESSAGE`.
    When no account holds it, ``confirmed`` must be true or the address is refused
    under ``confirmed`` with :data:`CONFIRM_MESSAGE`.  ``filters`` and ``columns`` are
    checked as :func:`checked_contents` checks them, ``formats`` is ``csv``, ``pdf`` or
    ``both``, ``cadence`` is ``weekly``, ``monthly``, ``quarterly`` or ``yearly``, and
    ``weekday`` is 0 (Monday) to 6 (Sunday).  The caller sets up the subscription,
    which is first due on the schedule's next day after today.
    """

    report = serializers.ChoiceField(choices=list(REPORTS))
    filters = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False)
    columns = serializers.ListField(child=serializers.CharField(), required=False)
    weekday = serializers.IntegerField(min_value=0, max_value=6, required=False)
    confirmed = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = ReportSubscription
        fields = [
            "report",
            "recipient_email",
            "filters",
            "columns",
            "formats",
            "cadence",
            "weekday",
            "confirmed",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Check the contents against the report, then bind or confirm the recipient."""
        spec = REPORTS[attrs["report"]]
        checked_contents(spec, attrs.get("filters", {}), attrs.get("columns", []))
        confirmed = attrs.pop("confirmed")
        user = User.objects.filter(email__iexact=attrs["recipient_email"]).first()
        if user is None:
            if not confirmed:
                raise serializers.ValidationError({"confirmed": [CONFIRM_MESSAGE]})
            return attrs
        subscription = ReportSubscription(recipient_user=user)
        if not recipient_may_read(subscription, spec):
            raise serializers.ValidationError({"recipient_email": [not_permitted(user)]})
        return {**attrs, "recipient_user": user, "recipient_email": user.email}

    def create(self, validated_data: dict[str, Any]) -> ReportSubscription:
        """Save it, set up by the ``creator`` context entry and due on its next day."""
        cadence = validated_data["cadence"]
        weekday = validated_data.get("weekday", 0)
        return ReportSubscription.objects.create(
            **validated_data,
            created_by=self.context["creator"],
            next_due_on=next_due_after(cadence, weekday, timezone.localdate()),
        )


class ReportRunRequestSerializer(serializers.Serializer[dict[str, bool]]):
    """The body of the two run endpoints: ``dry_run``, false when absent."""

    dry_run = serializers.BooleanField(default=False)


class ReportRunResultSerializer(serializers.Serializer[dict[str, Any]]):
    """What one run of the sender did, or would do: the counts, the reasons, the emails.

    ``skipped_by_reason`` holds one entry per reason that occurred: ``not_permitted``,
    ``no_recipients`` or ``no_email``.  Each action is kind ``report`` (the recipient,
    and the report's title and formats in ``detail``) or ``roster`` (the person, and
    the DART in ``detail``).
    """

    sent = serializers.IntegerField()
    skipped = serializers.IntegerField()
    failed = serializers.IntegerField()
    skipped_by_reason = serializers.DictField(child=serializers.IntegerField())
    actions = RunActionSerializer(many=True)


class RosterSerializer(serializers.ModelSerializer[Dart]):
    """One active DART's roster: who receives it, and when it last went out.

    ``roster_recipients`` counts the people ticked to receive it who have an address;
    ``roster_sent_at`` is null until the first roster goes out.
    """

    dart_id = serializers.IntegerField(source="pk", read_only=True)
    roster_recipients = serializers.SerializerMethodField()

    class Meta:
        model = Dart
        fields = ["dart_id", "name", "roster_recipients", "roster_sent_at"]
        read_only_fields = fields

    def get_roster_recipients(self, dart: Dart) -> int:
        """How many of the DART's people receive its roster."""
        return len(dart.roster_recipients())
