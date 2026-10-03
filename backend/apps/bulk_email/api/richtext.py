"""The endpoints behind the bulk email editor: the field catalog and image uploads.

``GET /bulk-email/fields`` lists the recipient fields the **Insert field** menu
offers, and ``POST /bulk-email/images`` stores one image the editor puts into a
message.  Both are CalDART management's (``management``); a system administrator
passes as for every role.  An anonymous caller is a 401, from
``caldart.exceptions``.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsManagement
from apps.bulk_email.fields import FIELDS, Field
from apps.bulk_email.images import ImageRefusedError, image_url, store
from apps.bulk_email.models import BulkEmailImage
from apps.members.api.actors import acting_user


class BulkEmailFieldSerializer(serializers.Serializer[Field]):
    """One recipient field: the token written in braces, its label, and what it holds."""

    token = serializers.CharField()
    # DRF's Field.label is a different thing from this serializer's own `label`
    # field, so the stubs see the declaration as a narrowing of the attribute.
    label = serializers.CharField()  # type: ignore[assignment]
    description = serializers.CharField()


class BulkEmailImageUploadSerializer(serializers.Serializer[dict[str, Any]]):
    """The body of an image upload: one file, ``image``, sent as multipart form data."""

    image = serializers.FileField()


class BulkEmailImageSerializer(serializers.ModelSerializer[BulkEmailImage]):
    """A stored image: its id, the absolute URL every copy links to, and its size."""

    url = serializers.SerializerMethodField()

    class Meta:
        model = BulkEmailImage
        fields = ["id", "url", "width", "height"]

    def get_url(self, image: BulkEmailImage) -> str:
        """The image's absolute URL on ``SITE_URL``'s host."""
        return image_url(image)


class FieldsView(APIView):
    """``GET /bulk-email/fields`` -- the recipient fields a message can fill in."""

    permission_classes = [IsManagement]

    @extend_schema(responses={200: BulkEmailFieldSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with every field in the catalog, in the order the menu lists them."""
        # djangorestframework-stubs does not model `many=True`, which wraps this
        # serializer in a ListSerializer taking the whole tuple.
        return Response(BulkEmailFieldSerializer(FIELDS, many=True).data)  # type: ignore[arg-type]


class ImageUploadView(APIView):
    """``POST /bulk-email/images`` -- store one image for a message."""

    permission_classes = [IsManagement]
    parser_classes = [MultiPartParser]

    @extend_schema(
        request={"multipart/form-data": BulkEmailImageUploadSerializer},
        responses={201: BulkEmailImageSerializer},
    )
    def post(self, request: Request) -> Response:
        """201 with the stored image; 400 under ``image`` for a file it refuses.

        The file is checked, scaled, and stored by ``apps.bulk_email.images.store``,
        with the caller as the uploader.  A missing file is DRF's *No file was
        submitted.*; a file too large, of the wrong type, or with too many pixels
        is refused with the reason in words.
        """
        payload = BulkEmailImageUploadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            image = store(payload.validated_data["image"], actor=acting_user(request))
        except ImageRefusedError as exc:
            raise ValidationError({"image": [str(exc)]}) from exc
        return Response(BulkEmailImageSerializer(image).data, status=status.HTTP_201_CREATED)
