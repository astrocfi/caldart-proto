"""The refund endpoint: giving money back against one payment.

The rules live in :mod:`apps.payments.refunds`, so the view does what every
other finance view does -- validate the body, call the service, render the
answer -- and the service is equally callable from a management command or a
test.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status as http_status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsFinance
from apps.payments.api.serializers import (
    RefundCreateSerializer,
    RefundIssuedSerializer,
)
from apps.payments.api.views import signed_in_user
from apps.payments.models import Payment
from apps.payments.providers.base import PaymentError
from apps.payments.refunds import issue_refund


class AdminPaymentRefundView(APIView):
    """``POST /admin/payments/{id}/refunds`` -- refund a payment, in part or in full."""

    permission_classes = [IsAuthenticated, IsFinance]

    @extend_schema(
        request=RefundCreateSerializer,
        responses={201: RefundIssuedSerializer},
    )
    def post(self, request: Request, payment_id: int) -> Response:
        """201 with ``{refund, payment}`` once the money has gone back.

        Only a treasurer or an account administrator may ask; anyone else gets
        403 and an unknown payment 404.  400 keyed by ``amount_cents`` when the
        amount is zero, exceeds what the payment has left unrefunded, or the
        payment never succeeded, keyed by ``reason`` for a reason outside the
        choices, and carrying ``detail`` when the provider refuses or cannot be
        reached.  ``payment`` is the row as it now stands, so the caller needs no
        second request to redraw it.
        """
        payment = get_object_or_404(Payment, pk=payment_id)
        serializer = RefundCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            refund = issue_refund(
                payment,
                amount_cents=data["amount_cents"],
                reason=data["reason"],
                note=data["note"],
                actor=signed_in_user(request),
                cancel_term=data["cancel_term"],
            )
        except PaymentError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        payment.refresh_from_db()
        body = RefundIssuedSerializer({"refund": refund, "payment": payment}).data
        return Response(body, status=http_status.HTTP_201_CREATED)
