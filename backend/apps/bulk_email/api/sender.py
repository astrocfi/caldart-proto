"""``POST /system/bulk-email/run``: the bulk email sender, run once by hand."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSystemAdmin
from apps.bulk_email.api.serializers import BulkEmailRunResultSerializer
from apps.bulk_email.job import REQUEST_BUDGET_SECONDS, run_sender
from apps.members.api.actors import acting_user
from caldart import audit


class SenderRunView(APIView):
    """``POST /system/bulk-email/run`` -- run the bulk email sender now."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(request=None, responses={200: BulkEmailRunResultSerializer})
    def post(self, request: Request) -> Response:
        """Run the sender once, in the request, and return what it did with status 200.

        It does what one run of the timer does, finishing any email left sending, then
        starting and sending every queued email whose start time has come, but for at
        most :data:`~apps.bulk_email.job.REQUEST_BUDGET_SECONDS`, inside the proxy's
        limit on a request.  An email still going then is left sending, and the timer's
        next run carries on with it.  The answer is ``{busy, emails, sent, failed,
        skipped, out_of_time, remaining, actions}``; ``busy`` is true when another run was
        working, and this one then did nothing, and ``out_of_time`` with ``remaining``
        says how many copies were left for the next run.  The caller is recorded as the
        actor on one ``bulk_email.run`` audit line with the counts.
        """
        run = run_sender(budget_seconds=REQUEST_BUDGET_SECONDS)
        audit.record(
            audit.BULK_EMAIL_RUN,
            actor=acting_user(request),
            busy=run.busy,
            emails=run.emails,
            sent=run.sent,
            failed=run.failed,
            skipped=run.skipped,
        )
        return Response(BulkEmailRunResultSerializer(run.as_dict()).data)
