"""The email log endpoints, and the bounce check run by hand.

``GET /system/emails``, ``GET /system/emails/purposes`` and ``POST
/system/bounces/run`` are ``system_admin`` only: the log carries every address the
installation has written to, which is operations work rather than membership work.
The filters live in ``apps.mail.filters``, which the ``emails`` report shares.
``GET /mail/delivery-check`` is the DNS check CalDART management reads before a bulk
send; it is open to ``management`` and ``system_admin``.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.accounts.api.views import signed_in_user
from apps.accounts.permissions import IsManagement, IsSystemAdmin
from apps.mail.api.serializers import (
    BounceRunRequestSerializer,
    BounceRunResultSerializer,
    EmailLogSerializer,
    EmailPurposeSerializer,
    MailDeliveryCheckSerializer,
)
from apps.mail.bounces import BounceCheckError, check_bounces
from apps.mail.dns_check import check_mail_dns
from apps.mail.filters import EmailLogFilterSet
from apps.mail.links import log_links
from apps.mail.models import EmailLog
from apps.mail.purposes import purpose_labels
from apps.mail.reports import order_email_log
from caldart.pagination import StandardPagination


class EmailLogListView(ListAPIView[EmailLog]):
    """``GET /system/emails`` -- paginated, newest first."""

    permission_classes = [IsSystemAdmin]
    serializer_class = EmailLogSerializer
    filterset_class = EmailLogFilterSet
    pagination_class = StandardPagination
    ordering_fields = ["sent_at"]

    def get_queryset(self) -> QuerySet[EmailLog]:
        """Return every email log row with its recipient account preloaded."""
        return EmailLog.objects.select_related("user").all()

    def get_serializer_context(self) -> dict[str, Any]:
        """The standard context plus ``purpose_labels``, read once for the whole page."""
        return {**super().get_serializer_context(), "purpose_labels": purpose_labels()}

    def get_serializer(self, *args: Any, **kwargs: Any) -> BaseSerializer[EmailLog]:
        """The serializer, with the page's ``log_links`` read once when it lists rows.

        Each row of a page links to the record it belongs to (``apps.mail.links``); the
        links of the whole page are read in one pass rather than row by row.
        """
        # A caller that hands its own context, as drf-spectacular does while it builds
        # the schema with no database, gets the serializer without one being read.
        if "context" in kwargs:
            return self.get_serializer_class()(*args, **kwargs)
        context = self.get_serializer_context()
        if kwargs.get("many") is True and len(args) > 0:
            rows = list(args[0])
            context["log_links"] = log_links(rows)
            args = (rows, *args[1:])
        # Not ``super()``: it reads the context afresh, and with it the purpose labels.
        return self.get_serializer_class()(*args, context=context, **kwargs)

    def filter_queryset[R](self, queryset: QuerySet[EmailLog, R]) -> QuerySet[EmailLog, R]:
        """Narrow ``queryset`` by the filters and put it in the download's order.

        Newest ``sent_at`` first unless ``?ordering=sent_at`` asks for oldest first;
        any other ``ordering`` is ignored.  Sends in the same instant follow their
        ``id`` in the same direction, so the pages and the ``emails`` report agree
        row for row.
        """
        # DRF's OrderingFilter (kept so the schema documents ``ordering``) replaces
        # ``EmailLog``'s ``-id`` tiebreak with the bare term; the report's order
        # puts it back.
        narrowed = super().filter_queryset(queryset)
        return order_email_log(narrowed, self.request.query_params.get("ordering", ""))


class EmailPurposeListView(APIView):
    """``GET /system/emails/purposes`` -- the purposes the log's filter offers."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(responses={200: EmailPurposeSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with one ``{value, label}`` per labeled purpose, in the filter's order.

        Unpaginated.  ``value`` is what ``?purpose=`` takes and ``label`` the words
        the portal shows for it; the renewal reminders' labels name the days of the
        stored reminder schedule.
        """
        rows = [{"value": value, "label": label} for value, label in purpose_labels().items()]
        # The stubs take the instance type from the single-object parameter, so
        # they do not widen it to a list when ``many`` is set.
        serializer = EmailPurposeSerializer(rows, many=True)  # type: ignore[arg-type]
        return Response(serializer.data)


class BounceRunView(APIView):
    """``POST /system/bounces/run`` -- run the bounce check now."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(
        request=BounceRunRequestSerializer,
        responses={
            200: BounceRunResultSerializer,
            400: OpenApiResponse(description="The bounce mailbox could not be read."),
        },
    )
    def post(self, request: Request) -> Response:
        """Run the check and return what it found with status 200.

        The body takes ``dry_run``, defaulting to ``False``; a dry run marks no email
        and no account and leaves every message in the mailbox unseen, and reports
        exactly what a live run would find.  The answer is ``{enabled, bounced,
        unmatched, ignored, skipped, actions}``; ``enabled`` is false when
        ``BOUNCE_IMAP_URL`` is empty.  The caller is recorded as the actor on the
        ``bounces.run`` audit record.  A malformed ``BOUNCE_IMAP_URL``, or a mailbox that
        cannot be reached, opened or read, is a 400 ``{"detail": <sentence>}`` naming the
        host and never the password.
        """
        payload = BounceRunRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            run = check_bounces(
                dry_run=payload.validated_data["dry_run"], actor=signed_in_user(request)
            )
        except BounceCheckError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BounceRunResultSerializer(run.as_dict()).data)


class MailDeliveryCheckView(APIView):
    """``GET /mail/delivery-check`` -- do the DNS records mail receivers trust exist?"""

    permission_classes = [IsManagement]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "refresh",
                bool,
                description="True to look the records up again instead of reading the cache.",
            )
        ],
        responses={200: MailDeliveryCheckSerializer},
    )
    def get(self, request: Request) -> Response:
        """200 with the report: ``{domain, checked_at, findings}``.

        ``findings`` holds one ``{name, status, detail, fix}`` per line in page order:
        the approved-sender list (SPF), the message signature (DKIM), the handling of
        forged mail (DMARC), and the bounce address.  A report made in the last five
        minutes is answered from the cache with its original ``checked_at``;
        ``?refresh=true`` runs the lookups again.  The lookups run in the request and
        wait at most three seconds each; a lookup that fails is a ``fail`` finding, never
        an error response.
        """
        refresh = request.query_params.get("refresh", "").lower() == "true"
        report = check_mail_dns(now=timezone.now(), refresh=refresh)
        return Response(
            MailDeliveryCheckSerializer(
                {
                    "domain": report.domain,
                    "checked_at": report.checked_at,
                    "findings": [asdict(finding) for finding in report.findings],
                }
            ).data
        )
