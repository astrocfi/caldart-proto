"""The template endpoints, **Start from a template**, and **Duplicate**.

Templates are CalDART management's alone (``management``; a system administrator
passes as for every role): ``/bulk-email/templates`` lists and saves them, and
``/bulk-email/templates/{id}`` reads, changes, and deletes one.
``POST /bulk-email/{id}/apply-template`` fills a draft from one.
``POST /bulk-email/{id}/duplicate`` copies any email the caller may open into a fresh
draft of their own.
"""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsManagement
from apps.bulk_email import templates
from apps.bulk_email.api.common import BULK_EMAIL_PERMISSIONS, email_for, refused
from apps.bulk_email.api.drafts import CONFLICT, detail_response
from apps.bulk_email.api.serializers import (
    BulkEmailDetailSerializer,
    checked_body,
    checked_subject,
)
from apps.bulk_email.drafts import NOT_SENDABLE_MESSAGE
from apps.bulk_email.models import EmailTemplate
from apps.mail.models import EmailType
from apps.mail.types import sendable_types
from apps.members.api.actors import acting_user
from caldart.exceptions import DomainError, DomainValidationError

#: The refusal of a template name another template has, ignoring case.
NAME_TAKEN_MESSAGE = 'A template named "{name}" already exists. Choose another name.'


class EmailTemplateSerializer(serializers.ModelSerializer[EmailTemplate]):
    """One saved template, as the Templates screen lists and edits it.

    ``name`` is required, at most 80 characters, trimmed, and unique ignoring case.
    ``subject`` and ``body`` follow a draft's rules (``PATCH /bulk-email/{id}``): one
    line of at most 200 characters, HTML of at most 100,000 characters saved
    sanitized, both may be blank, and neither may carry a recipient field token that
    cannot be filled in.  ``email_type`` is the id of a type the caller may send, or
    null; ``email_type_name`` its name, blank for none.  ``reply_to`` is an address,
    blank for the default.  ``created_by`` is the display name of who saved it, blank
    once that account is gone; it and the times are read-only.
    """

    subject = serializers.CharField(max_length=200, allow_blank=True, required=False)
    body = serializers.CharField(max_length=100_000, allow_blank=True, required=False)
    email_type = serializers.PrimaryKeyRelatedField(
        queryset=EmailType.objects.all(), required=False, allow_null=True
    )
    email_type_name = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = EmailTemplate
        fields = [
            "id",
            "name",
            "subject",
            "body",
            "email_type",
            "email_type_name",
            "reply_to",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value: str) -> str:
        """Refuse a name another template has, ignoring case."""
        others = EmailTemplate.objects.filter(name__iexact=value)
        if self.instance is not None:
            others = others.exclude(pk=self.instance.pk)
        if others.exists():
            raise ValidationError(NAME_TAKEN_MESSAGE.format(name=value))
        return value

    def validate_subject(self, value: str) -> str:
        """Refuse a subject a draft would refuse."""
        return checked_subject(value)

    def validate_body(self, value: str) -> str:
        """Sanitize the message, refusing one a draft would refuse."""
        return checked_body(value)

    def validate_email_type(self, value: EmailType | None) -> EmailType | None:
        """Refuse a type the caller may not send."""
        if value is not None and value not in sendable_types(acting_user(self.context["request"])):
            raise ValidationError(NOT_SENDABLE_MESSAGE.format(type=value.name))
        return value

    def get_email_type_name(self, template: EmailTemplate) -> str:
        """The type's name, or ``""`` for none."""
        return template.email_type.name if template.email_type is not None else ""

    def get_created_by(self, template: EmailTemplate) -> str:
        """Who saved the template, or ``""`` once that account is gone."""
        return template.created_by.display_name if template.created_by is not None else ""


class ApplyTemplateSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /bulk-email/{id}/apply-template``'s body: the template's id."""

    template = serializers.PrimaryKeyRelatedField(queryset=EmailTemplate.objects.all())


class DuplicateSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /bulk-email/{id}/duplicate``'s body: whether to copy the batch too."""

    copy_recipients = serializers.BooleanField(required=False, default=False)


def _templates() -> QuerySet[EmailTemplate]:
    """Every template by name, with its type and its author."""
    return EmailTemplate.objects.select_related("email_type", "created_by")


class TemplateListCreateView(generics.ListCreateAPIView[EmailTemplate]):
    """``GET/POST /bulk-email/templates`` -- every template by name; save one."""

    permission_classes = [IsManagement]
    serializer_class = EmailTemplateSerializer
    # CalDART keeps a handful of templates: the whole list is one short page.
    pagination_class = None
    queryset = EmailTemplate.objects.none()

    def get_queryset(self) -> QuerySet[EmailTemplate]:
        """Every template, by name ignoring case."""
        return _templates()

    def perform_create(self, serializer: serializers.BaseSerializer[EmailTemplate]) -> None:
        """Save the template with the caller as its author."""
        serializer.save(created_by=acting_user(self.request))


class TemplateDetailView(generics.RetrieveUpdateDestroyAPIView[EmailTemplate]):
    """``GET/PATCH/DELETE /bulk-email/templates/{id}`` -- one template."""

    permission_classes = [IsManagement]
    serializer_class = EmailTemplateSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]
    queryset = EmailTemplate.objects.none()

    def get_queryset(self) -> QuerySet[EmailTemplate]:
        """Every template, with its type and its author."""
        return _templates()


class ApplyTemplateView(APIView):
    """``POST /bulk-email/{id}/apply-template`` -- fill a draft from a template."""

    permission_classes = [IsManagement]

    @extend_schema(
        request=ApplyTemplateSerializer,
        responses={200: BulkEmailDetailSerializer, 409: CONFLICT},
    )
    def post(self, request: Request, pk: int) -> Response:
        """200 with the email, its subject, message, and type the template's.

        An unknown template is a 400 keyed ``template``; an email that has started
        sending is a 409.
        """
        bulk = email_for(request, pk)
        payload = ApplyTemplateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            filled = templates.apply_template(
                bulk, payload.validated_data["template"], actor=acting_user(request)
            )
        except DomainValidationError:
            raise
        except DomainError as error:
            return refused(error)
        return detail_response(filled)


class DuplicateView(APIView):
    """``POST /bulk-email/{id}/duplicate`` -- a fresh draft copied from an email."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(request=DuplicateSerializer, responses={201: BulkEmailDetailSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """201 with the fresh draft, the caller's own; the original is not changed.

        A DART leader reaches only their own emails (404 for any other), and one whose
        profile names no DART is a 403 saying so.
        """
        bulk = email_for(request, pk)
        payload = DuplicateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        copy = templates.duplicate(
            bulk,
            actor=acting_user(request),
            copy_recipients=payload.validated_data["copy_recipients"],
        )
        return detail_response(copy, code=status.HTTP_201_CREATED)
