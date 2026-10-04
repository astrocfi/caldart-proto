"""The finance area's renewals list as a CSV and a PDF.

The ``renewals`` report is the table of standing authorities on the Renewals tab, as a
file: automatic renewals and recurring donations alike, narrowed by the same status,
kind, and search the tab takes, in the same order, newest first, with one column
registry that the column chooser and both formats share.  The house style lives in
``caldart.reports``; this module only decides what a row prints and which rows the
report holds.
"""

from __future__ import annotations

from functools import reduce
from operator import or_
from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework import serializers

from apps.payments.models import MandateStatus, RenewalMandate
from apps.payments.renewals.schedule import (
    MandateKind,
    charge_date,
    mandate_kind,
    renewal_amount_cents,
)
from apps.payments.reports import FINANCE_ROLES
from caldart.reports import Money, Params, ReportColumn, ReportQuery, ReportSpec, given_params

#: Which mandates each ``kind`` value keeps: a renewal alone, a renewal with a
#: contribution, or a recurring donation, which renews no plan.
KIND_FILTERS: dict[str, Q] = {
    MandateKind.CONTRIBUTION: Q(plan__isnull=True),
    MandateKind.BOTH: Q(plan__isnull=False, contribution_cents__gt=0),
    MandateKind.RENEWAL: Q(plan__isnull=False, contribution_cents=0),
}

#: The fields ``search`` looks in, as the list's search does: every word of the search
#: must appear, without regard to case, in one of them.
SEARCH_FIELDS: tuple[str, ...] = (
    "user__email",
    "user__first_name",
    "user__last_name",
    "method_label",
)

#: The words each status prints, as the Renewals tab shows them.
STATUS_LABELS: dict[str, str] = {
    MandateStatus.PENDING: "Waiting for the first payment",
    MandateStatus.ACTIVE: "On",
    MandateStatus.PAUSED: "Paused after failed charges",
    MandateStatus.CANCELED: "Turned off",
}


class RenewalStatusFilterSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /admin/renewals?status=&kind=`` -- an empty value narrows nothing.

    ``kind`` is one of the mandate kinds the rows carry: ``renewal``, ``both`` or
    ``contribution`` (a recurring donation).
    """

    status = serializers.CharField(required=False, allow_blank=True, default="")
    kind = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_status(self, value: str) -> str:
        """Return ``value``, or raise ``Unknown status '<value>'.`` for an unknown one."""
        if value and value not in MandateStatus.values:
            raise serializers.ValidationError(f"Unknown status '{value}'.")
        return value

    def validate_kind(self, value: str) -> str:
        """Return ``value``, or raise ``Unknown kind '<value>'.`` for an unknown one."""
        if value and value not in MandateKind.values:
            raise serializers.ValidationError(f"Unknown kind '{value}'.")
        return value


#: The filters the PDF subtitle names, in order, when they carry a value.
EXPORT_FILTER_PARAMS: tuple[str, ...] = ("status", "kind", "search")


def mandate_queryset(params: Params) -> QuerySet[RenewalMandate]:
    """Every mandate ``params`` keep, newest first, with what each row reads fetched.

    ``status`` keeps the mandates in that state and ``kind`` those of that kind
    (``renewal``, ``both``, or ``contribution``); either blank keeps every one.  A
    value outside those raises DRF's ``ValidationError`` keyed by the parameter, reading
    ``Unknown status '<value>'.`` or ``Unknown kind '<value>'.``.  ``search`` keeps a
    mandate when every word of it appears, ignoring case, in the member's email, first
    name, or last name, or in the saved method's label.  The list endpoint and the
    report both narrow through this, so the two can never disagree.
    """
    query = RenewalStatusFilterSerializer(data=params)
    query.is_valid(raise_exception=True)
    queryset = RenewalMandate.objects.select_related("user", "plan").prefetch_related(
        "attempts", "user__memberships"
    )
    status = query.validated_data["status"]
    if status:
        queryset = queryset.filter(status=status)
    kind = query.validated_data["kind"]
    if kind:
        queryset = queryset.filter(KIND_FILTERS[kind])
    for word in params.get("search", "").split():
        queryset = queryset.filter(
            reduce(or_, (Q(**{f"{field}__icontains": word}) for field in SEARCH_FIELDS))
        )
    return queryset.order_by("-created_at", "-id")


def _iso(mandate: RenewalMandate) -> str:
    """The day of the mandate's next charge as ``YYYY-MM-DD``, or a blank cell."""
    day = charge_date(mandate)
    return day.isoformat() if day is not None else ""


#: Every column the renewals report can carry, in export order.  The defaults are the
#: Renewals tab's own columns; the cadence, the failures in a row, and the day the
#: authority was given are there for a closer look.
RENEWAL_REPORT_COLUMNS: tuple[ReportColumn[RenewalMandate], ...] = (
    ReportColumn("name", "Member", True, lambda row: row.user.display_name, width=2.6),
    ReportColumn("email", "Email", True, lambda row: row.user.email, width=3.6),
    ReportColumn("kind", "Type", True, lambda row: MandateKind(mandate_kind(row)).label, width=3.0),
    ReportColumn("cadence", "Cadence", False, lambda row: row.get_cadence_display(), width=1.4),
    ReportColumn(
        "plan", "Plan", True, lambda row: row.plan.name if row.plan is not None else "", width=1.8
    ),
    ReportColumn(
        "amount", "Next charge", True, lambda row: Money(renewal_amount_cents(row)), width=1.6
    ),
    ReportColumn("next_charge_on", "Due", True, _iso, width=1.6),
    ReportColumn("method", "Method", True, lambda row: row.method_label, width=2.4),
    ReportColumn("status", "Status", True, lambda row: STATUS_LABELS[row.status], width=1.8),
    ReportColumn("failures", "Failed charges", False, lambda row: row.failure_count, width=1.4),
    ReportColumn(
        "started_on",
        "Started",
        False,
        lambda row: timezone.localdate(row.created_at).isoformat(),
        width=1.6,
    ),
)


def renewal_report_query(params: Params) -> ReportQuery[RenewalMandate]:
    """The mandates for ``params``, as :func:`mandate_queryset` narrows them.

    The applied filters are those of :data:`EXPORT_FILTER_PARAMS` given a value.
    """
    return ReportQuery(
        rows=mandate_queryset(params),
        filters=given_params(params, EXPORT_FILTER_PARAMS),
    )


#: The renewals list, for the finance roles.
RENEWAL_REPORT: ReportSpec[RenewalMandate] = ReportSpec(
    slug="renewals",
    title="CalDART renewals",
    filename_stem="caldart-renewals",
    columns=RENEWAL_REPORT_COLUMNS,
    roles=FINANCE_ROLES,
    query=renewal_report_query,
)
