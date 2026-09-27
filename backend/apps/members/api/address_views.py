"""``GET /addresses/suggest``: street-address suggestions for the profile form.

Any signed-in account may ask, at the rate ``ADDRESS_SUGGEST_THROTTLE_RATE`` allows.
The view validates the query and hands it to
:func:`apps.members.addresses.suggest_addresses`, which calls Geoapify on the server's
key; the key never appears in a response.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.members.addresses import AddressSuggestion, suggest_addresses
from apps.members.throttling import AddressSuggestThrottle

#: The longest query accepted; a street line is at most 200 characters on the profile.
MAX_QUERY_LENGTH = 200


class AddressSuggestQuerySerializer(serializers.Serializer[dict[str, str]]):
    """The query string: ``q``, the street line so far, at most 200 characters."""

    q = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=True, max_length=MAX_QUERY_LENGTH
    )


class AddressSuggestionSerializer(serializers.Serializer[AddressSuggestion]):
    """One suggested address: a one-line label and the five profile fields it fills."""

    # DRF's Field.label is a different thing from this serializer's own `label`
    # field, so the stubs see the declaration as a narrowing of the attribute.
    label = serializers.CharField()  # type: ignore[assignment]
    address_line1 = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    postal_code = serializers.CharField()
    county = serializers.CharField()


class AddressSuggestView(APIView):
    """``GET /addresses/suggest?q=`` -- addresses matching the street line typed."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [AddressSuggestThrottle]

    @extend_schema(
        parameters=[OpenApiParameter("q", str, description="The street line typed so far.")],
        responses={200: AddressSuggestionSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        """200 with up to five suggestions, or ``[]``; 400 when ``q`` is too long.

        The list is empty when the feature is off (no ``GEOAPIFY_API_KEY``), when ``q``
        is missing or shorter than three characters, and when Geoapify cannot be
        reached or answers badly.  Past the throttle's rate the answer is 429.
        """
        query = AddressSuggestQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        suggestions = suggest_addresses(query.validated_data.get("q", ""))
        # The DRF stubs type a serializer's instance as one item even with many=True.
        rows = AddressSuggestionSerializer(suggestions, many=True)  # type: ignore[arg-type]
        return Response(rows.data)
