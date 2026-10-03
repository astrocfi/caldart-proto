"""The checks before a send: ``POST /bulk-email/{id}/checks`` and ``.../test``.

``checks`` lists what ``apps.bulk_email.checks.run_checks`` finds in the saved email,
and ``test`` mails the caller a test copy of it (``apps.bulk_email.tests_send``).  An
email the checks find errors in is a 400 ``{"checks": [...]}`` from ``test``, as it is
from ``send``.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bulk_email.api.common import BULK_EMAIL_PERMISSIONS, email_for
from apps.bulk_email.checks import ChecksFailedError, Finding, Level, run_checks
from apps.bulk_email.tests_send import send_test
from apps.bulk_email.throttling import BulkEmailChecksThrottle
from apps.members.api.actors import acting_user
from caldart.mail import MailRefusedError, log_refusal

#: The answer to a test copy the mail server refused.
TEST_REFUSED_MESSAGE = "The mail server refused the test. Try again in a minute."


class BulkEmailFindingSerializer(serializers.Serializer[Finding]):
    """One finding of the checks: its ``code``, its ``level``, and its ``message``."""

    code = serializers.CharField()
    level = serializers.ChoiceField(choices=Level.choices)
    message = serializers.CharField()


class BulkEmailChecksRefusalSerializer(serializers.Serializer[dict[str, list[Finding]]]):
    """The 400 of an email the checks find errors in: the errors under ``checks``."""

    checks = BulkEmailFindingSerializer(many=True)


class BulkEmailTestResultSerializer(serializers.Serializer[dict[str, str]]):
    """Where a test copy went: ``to``, the caller's own address."""

    to = serializers.EmailField()


#: The answer to an email the checks find errors in.
CHECKS_REFUSED = OpenApiResponse(
    response=BulkEmailChecksRefusalSerializer,
    description="The checks found errors; they are listed under checks.",
)


def checks_refused(error: ChecksFailedError) -> Response:
    """400 ``{"checks": [<finding>, ...]}``: the errors that keep the email from going."""
    # The stubs type a serializer's instance as one object, even with ``many=True``.
    findings = BulkEmailFindingSerializer(error.findings, many=True)  # type: ignore[arg-type]
    payload = {"checks": findings.data}
    return Response(payload, status=status.HTTP_400_BAD_REQUEST)


class ChecksView(APIView):
    """``POST /bulk-email/{id}/checks`` -- what the checks find in the saved email."""

    permission_classes = BULK_EMAIL_PERMISSIONS
    throttle_classes = [BulkEmailChecksThrottle]

    @extend_schema(request=None, responses={200: BulkEmailFindingSerializer(many=True)})
    def post(self, request: Request, pk: int) -> Response:
        """200 with every finding, errors first; an empty list when nothing is wrong.

        The links in the message are fetched to see whether they load, so the answer
        can take several seconds, at most about 30.  404 for an email the caller may
        not open; 429 past ``BULK_EMAIL_CHECKS_THROTTLE_RATE`` for the caller.
        """
        bulk = email_for(request, pk)
        # The stubs type a serializer's instance as one object, even with ``many=True``.
        findings = BulkEmailFindingSerializer(run_checks(bulk), many=True)  # type: ignore[arg-type]
        return Response(findings.data)


class TestSendView(APIView):
    """``POST /bulk-email/{id}/test`` -- mail the caller a test copy of the email."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(
        request=None,
        responses={
            200: BulkEmailTestResultSerializer,
            400: CHECKS_REFUSED,
            503: OpenApiResponse(description="The mail server refused the test."),
        },
    )
    def post(self, request: Request, pk: int) -> Response:
        """200 ``{"to": <address>}`` once a test copy went to the caller.

        Every call sends one more copy.  400 ``{"checks": [...]}`` when the checks find
        errors, and 503 :data:`TEST_REFUSED_MESSAGE` when the mail server refuses the
        copy; 404 for an email the caller may not open.
        """
        bulk = email_for(request, pk)
        actor = acting_user(request)
        try:
            address = send_test(bulk, actor=actor)
        except ChecksFailedError as error:
            return checks_refused(error)
        except MailRefusedError as refusal:
            log_refusal(f"the test copy of bulk email {bulk.pk} for account {actor.pk}", refusal)
            return Response(
                {"detail": TEST_REFUSED_MESSAGE}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response({"to": address})
