"""Receipts and annual contribution statements, for a member and for finance.

A member downloads their own receipts and statements; the finance roles reach
any member's, and can send a receipt again when the first one did not arrive.
Everything here answers with a PDF built by :mod:`apps.payments.receipts`,
except the two JSON endpoints that say which years and what came of a resend.

A receipt exists only for money that arrived, so a pending or failed payment has
none and answers 404, exactly as an unknown id does.
"""

from __future__ import annotations

from typing import cast

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsFinance
from apps.payments import receipts
from apps.payments.api.serializers import ReceiptSendSerializer, StatementYearsSerializer
from apps.payments.models import Payment
from caldart import audit
from caldart.reports import PDF_MEDIA_TYPE, download_responses


def _pdf_download(filename: str, body: bytes) -> HttpResponse:
    """A rendered PDF as an attachment under ``filename``."""
    response = HttpResponse(body, content_type=PDF_MEDIA_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _settled_payment(payment_id: int, *, user: User | None = None) -> Payment:
    """The settled payment ``payment_id``, or 404.

    ``user`` narrows the search to that member's own payments, which is what
    makes the member's endpoints owner-only: somebody else's payment is as
    invisible as one that does not exist.  A payment whose money never arrived
    has no receipt, so it is a 404 too.
    """
    payments = Payment.objects.select_related("user", "plan")
    if user is not None:
        payments = payments.filter(user=user)
    return get_object_or_404(payments, pk=payment_id, status__in=receipts.SETTLED_STATUSES)


def _statement_download(member: User, year: int) -> HttpResponse:
    """``member``'s statement for ``year`` as a download, or 404.

    A year the member contributed nothing in has no statement, and answers 404
    rather than a page of zeroes.
    """
    if year not in receipts.statement_years(member):
        raise Http404("No contributions in that year.")
    return _pdf_download(
        receipts.statement_filename(member, year), receipts.render_statement_pdf(member, year)
    )


def _signed_in_user(request: Request) -> User:
    """The member behind a request ``IsAuthenticated`` has already let through."""
    return cast(User, request.user)


# --------------------------------------------------------------------------
# A member's own receipts and statements
# --------------------------------------------------------------------------
class MyReceiptView(APIView):
    """``GET /me/payments/{id}/receipt.pdf`` -- the caller's own receipt."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=download_responses(PDF_MEDIA_TYPE, "The receipt for one payment."))
    def get(self, request: Request, pk: int) -> HttpResponse:
        """200 with the receipt PDF as an attachment, for the payer alone.

        401 when anonymous, and 404 for an unknown payment, for one belonging to
        somebody else, and for one whose money never arrived.
        """
        payment = _settled_payment(pk, user=_signed_in_user(request))
        return _pdf_download(
            receipts.receipt_filename(payment), receipts.render_receipt_pdf(payment)
        )


class MyStatementYearsView(APIView):
    """``GET /me/payments/statements`` -- the years the caller may download."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: StatementYearsSerializer})
    def get(self, request: Request) -> Response:
        """200 with ``{"years": [...]}``, newest first; 401 when anonymous.

        A member who has never contributed gets an empty list, not a 404.
        """
        years = receipts.statement_years(_signed_in_user(request))
        return Response(StatementYearsSerializer({"years": years}).data)


class MyStatementView(APIView):
    """``GET /me/payments/statements/{year}.pdf`` -- the caller's own statement."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=download_responses(PDF_MEDIA_TYPE, "One year of the caller's contributions.")
    )
    def get(self, request: Request, year: int) -> HttpResponse:
        """200 with the statement PDF; 401 when anonymous; 404 for a year with none."""
        return _statement_download(_signed_in_user(request), year)


# --------------------------------------------------------------------------
# The finance roles: any member's receipts and statements
# --------------------------------------------------------------------------
class AdminReceiptView(APIView):
    """``GET /admin/payments/{id}/receipt.pdf`` -- any member's receipt."""

    permission_classes = [IsAuthenticated, IsFinance]

    @extend_schema(responses=download_responses(PDF_MEDIA_TYPE, "The receipt for one payment."))
    def get(self, request: Request, pk: int) -> HttpResponse:
        """200 with the receipt PDF as an attachment, for a treasurer or an account admin.

        401 when anonymous, 403 for any other role, and 404 for an unknown
        payment or one whose money never arrived.
        """
        payment = _settled_payment(pk)
        return _pdf_download(
            receipts.receipt_filename(payment), receipts.render_receipt_pdf(payment)
        )


class AdminReceiptSendView(APIView):
    """``POST /admin/payments/{id}/receipt`` -- send the receipt again."""

    permission_classes = [IsAuthenticated, IsFinance]

    @extend_schema(request=None, responses={200: ReceiptSendSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """200 with ``{sent, receipt_sent_at}``, for a treasurer or an account admin.

        The receipt is built afresh and emailed to the payer with its PDF
        attached, and ``receipt_sent_at`` is stamped when it goes.  A mail server
        that refuses it answers ``sent: false`` with the stamp unchanged, so the
        same button is the retry.  401 when anonymous, 403 for any other role,
        and 404 for an unknown payment or one whose money never arrived.
        """
        payment = _settled_payment(pk)
        sent = receipts.send_receipt(payment)
        audit.record(
            audit.PAYMENT_RECEIPT_RESEND,
            actor=_signed_in_user(request),
            target=payment,
            sent=sent,
        )
        payment.refresh_from_db(fields=["receipt_sent_at"])
        serializer = ReceiptSendSerializer(
            {"sent": sent, "receipt_sent_at": payment.receipt_sent_at}
        )
        return Response(serializer.data)


class AdminMemberStatementView(APIView):
    """``GET /admin/payments/ledger/{user_id}/statements/{year}.pdf``."""

    permission_classes = [IsAuthenticated, IsFinance]

    @extend_schema(
        responses=download_responses(PDF_MEDIA_TYPE, "One year of a member's contributions.")
    )
    def get(self, request: Request, user_id: int, year: int) -> HttpResponse:
        """200 with the member's statement PDF, for a treasurer or an account admin.

        401 when anonymous, 403 for any other role, 404 for an unknown member and
        for a year they contributed nothing in.
        """
        member = get_object_or_404(User, pk=user_id)
        return _statement_download(member, year)
