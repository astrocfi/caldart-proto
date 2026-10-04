"""The email types and every person's email preferences.

``/email-types`` and ``/email-types/{id}`` are the system administrator's: the kinds
of bulk email, who may send each, and whether each may be turned off.
``/email-types/sendable`` answers any signed-in caller with the types they may send.
``/me/email-preferences`` is every signed-in person's own choice of the types they
receive, and ``/admin/members/{id}/email-preferences`` the account administrator's
view and change of somebody else's.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.views import signed_in_user
from apps.accounts.models import User
from apps.accounts.permissions import IsAccountAdmin, IsSystemAdmin
from apps.mail.api.type_serializers import (
    EmailPreferenceChangeSerializer,
    EmailPreferenceSerializer,
    EmailTypeSerializer,
    SendableEmailTypeSerializer,
)
from apps.mail.models import EmailType, OptOutSource
from apps.mail.types import (
    create_type,
    delete_type,
    list_types,
    opt_out_records,
    opt_out_types,
    sendable_types,
    set_opt_out,
    update_type,
)
from apps.members.services import TOMBSTONE_CHANGE_REFUSED, is_tombstone
from caldart import audit
from caldart.exceptions import DomainError

#: The refusal for a change naming a type that does not exist, or cannot be turned off.
UNKNOWN_PREFERENCE = "That email type does not exist, or cannot be turned off."

#: The refusal for a change list that names one type twice.
REPEATED_PREFERENCE = "Name each email type once."


class EmailTypeListView(APIView):
    """``GET | POST /email-types`` -- every type, and adding one."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(responses={200: EmailTypeSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with every type, unpaginated, in ``position`` order and then by name."""
        return Response(EmailTypeSerializer(list_types(), many=True).data)

    @extend_schema(request=EmailTypeSerializer, responses={201: EmailTypeSerializer})
    def post(self, request: Request) -> Response:
        """201 with the type created from the body, audited as ``email_type.create``.

        ``name``, ``description``, ``allow_opt_out`` and ``sender_roles`` are required
        and ``position`` optional.  A name another type holds, ignoring case and
        punctuation, is a 400 ``{"name": ["Another email type already has this
        name."]}``; a role other than ``dart_leader`` or ``management`` is a 400 on
        ``sender_roles``.
        """
        serializer = EmailTypeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email_type = create_type(serializer.to_fields(), actor=signed_in_user(request))
        return Response(EmailTypeSerializer(email_type).data, status=status.HTTP_201_CREATED)


class EmailTypeDetailView(APIView):
    """``PUT | DELETE /email-types/{id}`` -- change a type, or delete one never used."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(request=EmailTypeSerializer, responses={200: EmailTypeSerializer})
    def put(self, request: Request, pk: int) -> Response:
        """200 with the type once the body has replaced its settings.

        The body is ``POST /email-types``'s, with the same refusals; the type's own name
        is never taken for another's.  Turning ``allow_opt_out`` off keeps every
        recorded opt-out for when it is turned back on.  Audited as
        ``email_type.update``.  An unknown id is a 404.
        """
        email_type = get_object_or_404(EmailType, pk=pk)
        serializer = EmailTypeSerializer(email_type, data=request.data)
        serializer.is_valid(raise_exception=True)
        update_type(email_type, serializer.to_fields(), actor=signed_in_user(request))
        return Response(EmailTypeSerializer(email_type).data)

    @extend_schema(
        request=None,
        responses={
            204: None,
            400: OpenApiResponse(description="A bulk email names the type."),
        },
    )
    def delete(self, request: Request, pk: int) -> Response:
        """204 once the type and every opt-out of it are gone, audited.

        A type a bulk email names cannot be deleted: the answer is 400 ``{"detail":
        "<name> has been used for a bulk email, so it cannot be deleted. To keep DART
        leaders and CalDART management from sending it, take their roles off it
        instead."}`` and nothing changes.  An unknown id is a 404.
        """
        email_type = get_object_or_404(EmailType, pk=pk)
        try:
            delete_type(email_type, actor=signed_in_user(request))
        except DomainError as error:
            return Response({"detail": error.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SendableEmailTypeListView(APIView):
    """``GET /email-types/sendable`` -- the types the caller may send."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SendableEmailTypeSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with the types whose ``sender_roles`` name one of the caller's roles.

        Every type for a system administrator; an empty list for a caller with no
        sending role.  Unpaginated, in ``position`` order and then by name.
        """
        types = sendable_types(signed_in_user(request))
        return Response(SendableEmailTypeSerializer(types, many=True).data)


class MyEmailPreferencesView(APIView):
    """``GET | PUT /me/email-preferences`` -- the caller's own choice of email."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: EmailPreferenceSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with one row per type that may be turned off, and the caller's choice.

        A type that does not allow opting out is not listed.
        """
        return _preferences(signed_in_user(request))

    @extend_schema(
        request=EmailPreferenceChangeSerializer(many=True),
        responses={200: EmailPreferenceSerializer(many=True)},
    )
    def put(self, request: Request) -> Response:
        """200 with every preference once the changes in the body are made.

        The body is a list of ``{"email_type": <id>, "opted_out": <bool>}``; a type it
        leaves out is left alone.  Each real change is audited as ``email.opt_out`` or
        ``email.opt_in`` with the source ``profile``.  A type that does not exist or
        cannot be turned off is a 400 ``{"email_type": ["That email type does not
        exist, or cannot be turned off."]}``, a list naming one type twice a 400
        ``{"email_type": ["Name each email type once."]}``, and nothing changes.
        """
        user = signed_in_user(request)
        _apply(user, _resolve(request.data), source=OptOutSource.PROFILE, actor=user)
        return _preferences(user)


class MemberEmailPreferencesView(APIView):
    """``GET | PUT /admin/members/{id}/email-preferences`` -- a member's choices."""

    permission_classes = [IsAccountAdmin]

    @extend_schema(responses={200: EmailPreferenceSerializer(many=True)})
    def get(self, request: Request, pk: int) -> Response:
        """200 with the member's preferences, as ``GET /me/email-preferences`` answers.

        An unknown member is a 404.
        """
        return _preferences(get_object_or_404(User, pk=pk))

    @extend_schema(
        request=EmailPreferenceChangeSerializer(many=True),
        responses={200: EmailPreferenceSerializer(many=True)},
    )
    def put(self, request: Request, pk: int) -> Response:
        """200 with the member's preferences once the changes in the body are made.

        The body and its refusals are ``PUT /me/email-preferences``'s; each change is
        audited with the caller as the actor and the source ``admin``.  A deleted
        member's record is a 400 ``{"detail": ...}`` with the sentence it refuses every
        change with, and each change asked for is audited at WARNING as the
        ``email.opt_out`` or ``email.opt_in`` it would have been, with the reason
        ``tombstone``.  An unknown member is a 404.
        """
        member = get_object_or_404(User, pk=pk)
        actor = signed_in_user(request)
        resolved = _resolve(request.data)
        if is_tombstone(member):
            for email_type, opted_out in resolved:
                audit.refuse(
                    audit.EMAIL_OPT_OUT if opted_out else audit.EMAIL_OPT_IN,
                    actor=actor,
                    target=member,
                    reason=audit.REASON_TOMBSTONE,
                    email_type=email_type.pk,
                )
            return Response(
                {"detail": TOMBSTONE_CHANGE_REFUSED}, status=status.HTTP_400_BAD_REQUEST
            )
        _apply(member, resolved, source=OptOutSource.ADMIN, actor=actor)
        return _preferences(member)


def _preferences(user: User) -> Response:
    """200 with ``user``'s choice for every type that may be turned off.

    A type turned off carries where and when that was recorded.
    """
    recorded = opt_out_records(user)
    rows = [
        {
            "email_type": email_type.pk,
            "name": email_type.name,
            "description": email_type.description,
            "opted_out": email_type.pk in recorded,
            "opted_out_source": (
                recorded[email_type.pk].source if email_type.pk in recorded else ""
            ),
            "opted_out_at": (
                recorded[email_type.pk].created_at if email_type.pk in recorded else None
            ),
        }
        for email_type in opt_out_types()
    ]
    # The stubs take the instance type from the single-object parameter, so they do
    # not widen it to a list when ``many`` is set.
    serializer = EmailPreferenceSerializer(rows, many=True)  # type: ignore[arg-type]
    return Response(serializer.data)


def _resolve(data: object) -> list[tuple[EmailType, bool]]:
    """The changes the request body ``data`` lists, each as a type and the choice.

    Raises a 400 ``ValidationError`` for a body that is not a list of changes, on
    ``email_type`` with :data:`UNKNOWN_PREFERENCE` for a type that does not exist or
    cannot be turned off, and with :data:`REPEATED_PREFERENCE` for a type named twice.
    """
    serializer = EmailPreferenceChangeSerializer(data=data, many=True)
    serializer.is_valid(raise_exception=True)
    changes: Iterable[Mapping[str, object]] = serializer.validated_data
    allowed = {email_type.pk: email_type for email_type in opt_out_types()}
    resolved: list[tuple[EmailType, bool]] = []
    named: set[int] = set()
    for change in changes:
        type_id = change["email_type"]
        if not isinstance(type_id, int) or type_id not in allowed:
            raise ValidationError({"email_type": [UNKNOWN_PREFERENCE]})
        if type_id in named:
            raise ValidationError({"email_type": [REPEATED_PREFERENCE]})
        named.add(type_id)
        resolved.append((allowed[type_id], bool(change["opted_out"])))
    return resolved


@transaction.atomic
def _apply(
    user: User, resolved: list[tuple[EmailType, bool]], *, source: OptOutSource, actor: User
) -> None:
    """Make each of the ``resolved`` changes to ``user``'s opt-outs, or none of them."""
    for email_type, opted_out in resolved:
        set_opt_out(user, email_type, opted_out=opted_out, source=source, actor=actor)
