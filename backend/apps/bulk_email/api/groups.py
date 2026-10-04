"""The recipient group endpoints, **Add a saved group**, and saving a batch as a group.

Every endpoint here is CalDART management's alone (``management``; a system
administrator passes as for every role).  ``/bulk-email/groups`` lists and makes
groups, ``/bulk-email/groups/{id}`` reads, renames, and deletes one, and the routes
under it list a group's people now, download them, and change a fixed group's people
or a live group's filters.  ``POST /bulk-email/{id}/batch/add-group`` adds a group to
a batch, and ``POST /bulk-email/{id}/save-group`` saves a batch as a group.

A change the group's kind does not allow, such as adding a person to a live group, is
a 409 ``{"detail": <sentence>}``.
"""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsManagement
from apps.bulk_email import groups
from apps.bulk_email.api.common import email_for, refused
from apps.bulk_email.api.drafts import CONFLICT
from apps.bulk_email.api.serializers import (
    BulkEmailAddResultSerializer,
    checked_filters,
)
from apps.bulk_email.batch import add_label
from apps.bulk_email.models import (
    GroupKind,
    RecipientGroup,
    RecipientGroupFilter,
    RecipientGroupMember,
)
from apps.members.api.actors import acting_user
from caldart.exceptions import DomainError, DomainValidationError
from caldart.reports import CSV_MEDIA_TYPE, download_responses, report_response

#: The refusal of a group name another group has, ignoring case.
NAME_TAKEN_MESSAGE = 'A group named "{name}" already exists. Choose another name.'

#: The refusal of changing a group's kind once it is made.
KIND_FIXED_MESSAGE = "A group's kind cannot change. Save a new group instead."

#: The answer to a change the group's kind does not allow.
WRONG_KIND = OpenApiResponse(description="The group's kind does not allow it; carries detail.")


def _checked_name(value: str, instance: RecipientGroup | None = None) -> str:
    """``value`` once no other group has it, ignoring case; else ``ValidationError``."""
    others = RecipientGroup.objects.filter(name__iexact=value)
    if instance is not None:
        others = others.exclude(pk=instance.pk)
    if others.exists():
        raise ValidationError(NAME_TAKEN_MESSAGE.format(name=value))
    return value


class RecipientGroupFilterSerializer(serializers.ModelSerializer[RecipientGroupFilter]):
    """One filter set of a live group: its filters in words and as given.

    ``needs_fixing`` is true when the member list no longer accepts the set as stored,
    such as a DART that has been deleted.
    """

    # ``Field`` has a ``label`` attribute of its own, which a field of that name shadows.
    label = serializers.SerializerMethodField()  # type: ignore[assignment]
    filters = serializers.DictField(child=serializers.CharField(), read_only=True)
    needs_fixing = serializers.SerializerMethodField()

    class Meta:
        model = RecipientGroupFilter
        fields = ["id", "label", "filters", "position", "needs_fixing"]
        read_only_fields = fields

    def get_needs_fixing(self, filter_set: RecipientGroupFilter) -> bool:
        """True when the member list refuses the set as stored."""
        return not groups.filters_work(filter_set.filters)

    def get_label(self, filter_set: RecipientGroupFilter) -> str:
        """The filters in words, such as ``"Kind: Friends only, County: Marin"``."""
        return add_label(filter_set.filters)


class RecipientGroupSerializer(serializers.ModelSerializer[RecipientGroup]):
    """One saved recipient group, as the Recipient groups screen lists and edits it.

    ``name`` is required, at most 80 characters, trimmed, and unique ignoring case.
    ``kind`` is ``fixed`` or ``live``, given when the group is made and never changed.
    ``count`` is how many people the group holds now, a live group's filters run
    afresh, and null when ``needs_fixing``: a live group one of whose stored filter
    sets the member list no longer accepts.  ``filter_sets`` are a live group's
    filters, empty for a fixed group.
    ``created_by`` is the display name of who made it, blank once that account is gone.
    """

    count = serializers.SerializerMethodField()
    needs_fixing = serializers.SerializerMethodField()
    filter_sets = RecipientGroupFilterSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = RecipientGroup
        fields = [
            "id",
            "name",
            "kind",
            "count",
            "needs_fixing",
            "filter_sets",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value: str) -> str:
        """Refuse a name another group has, ignoring case."""
        return _checked_name(value, self.instance)

    def validate_kind(self, value: str) -> str:
        """Refuse a change of kind to a group that exists."""
        if self.instance is not None and value != self.instance.kind:
            raise ValidationError(KIND_FIXED_MESSAGE)
        return value

    def get_count(self, group: RecipientGroup) -> int | None:
        """How many people the group holds now; null while its filters need fixing."""
        return groups.group_count(group)

    def get_needs_fixing(self, group: RecipientGroup) -> bool:
        """True when the member list refuses one of a live group's stored filters."""
        return any(
            not groups.filters_work(filter_set.filters) for filter_set in group.filter_sets.all()
        )

    def get_created_by(self, group: RecipientGroup) -> str:
        """Who made the group, or ``""`` once that account is gone."""
        return group.created_by.display_name if group.created_by is not None else ""


class GroupPersonSerializer(serializers.Serializer[groups.GroupPerson]):
    """One person in a group now: the account, its name, address, kind, and DART.

    ``is_active`` is false for a deactivated account, which a send skips.
    """

    user_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.CharField()
    kind = serializers.CharField()
    dart_name = serializers.CharField(allow_blank=True)
    is_active = serializers.BooleanField()


class GroupPeopleSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /bulk-email/groups/{id}/members``: how many people, and each of them."""

    count = serializers.IntegerField()
    people = GroupPersonSerializer(many=True)


class GroupMemberAddSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /bulk-email/groups/{id}/members``'s body: the account to add."""

    user = serializers.IntegerField()


class GroupFilterAddSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /bulk-email/groups/{id}/filters``'s body: one set of member list filters.

    Blank filters are ignored; left out, or empty, the set chooses every member and
    friend.
    """

    filters = serializers.DictField(
        child=serializers.CharField(allow_blank=True), required=False, default=dict
    )

    def validate_filters(self, value: dict[str, str]) -> dict[str, str]:
        """Refuse a filter the member list does not have, or a value it refuses."""
        return checked_filters(value)


class AddGroupSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /bulk-email/{id}/batch/add-group``'s body: the group's id."""

    group = serializers.PrimaryKeyRelatedField(queryset=RecipientGroup.objects.all())


class SaveGroupSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /bulk-email/{id}/save-group``'s body: the group's name and kind."""

    name = serializers.CharField(max_length=80)
    kind = serializers.ChoiceField(choices=GroupKind.choices)

    def validate_name(self, value: str) -> str:
        """Refuse a name another group has, ignoring case."""
        return _checked_name(value)


class PersonMatchSerializer(serializers.ModelSerializer[User]):
    """One member or friend the search found: the account, its name, and its address."""

    name = serializers.CharField(source="display_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "name", "email"]
        read_only_fields = fields


def _groups() -> QuerySet[RecipientGroup]:
    """Every group by name, with its author and its filter sets."""
    return RecipientGroup.objects.select_related("created_by").prefetch_related("filter_sets")


def _group(pk: int) -> RecipientGroup:
    """The group ``pk``; ``Http404`` when there is none."""
    return get_object_or_404(_groups(), pk=pk)


def _people_payload(group: RecipientGroup) -> dict[str, Any]:
    """``group``'s people now, as ``GET /bulk-email/groups/{id}/members`` answers."""
    people = groups.group_people(group)
    return {"count": len(people), "people": people}


class GroupListCreateView(generics.ListCreateAPIView[RecipientGroup]):
    """``GET/POST /bulk-email/groups`` -- every group by name; make an empty one."""

    permission_classes = [IsManagement]
    serializer_class = RecipientGroupSerializer
    # CalDART keeps a handful of groups: the whole list is one short page.
    pagination_class = None
    queryset = RecipientGroup.objects.none()

    def get_queryset(self) -> QuerySet[RecipientGroup]:
        """Every group, by name ignoring case."""
        return _groups()

    def perform_create(self, serializer: serializers.BaseSerializer[RecipientGroup]) -> None:
        """Save the group, with nobody and no filters in it, the caller as its author."""
        serializer.save(created_by=acting_user(self.request))


class GroupDetailView(generics.RetrieveUpdateDestroyAPIView[RecipientGroup]):
    """``GET/PATCH/DELETE /bulk-email/groups/{id}`` -- one group.

    Deleting a group leaves every batch it was added to as it is.
    """

    permission_classes = [IsManagement]
    serializer_class = RecipientGroupSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]
    queryset = RecipientGroup.objects.none()

    def get_queryset(self) -> QuerySet[RecipientGroup]:
        """Every group, with its author and its filter sets."""
        return _groups()


class GroupPeopleView(APIView):
    """``GET/POST /bulk-email/groups/{id}/members`` -- the people now; add one."""

    permission_classes = [IsManagement]

    @extend_schema(responses={200: GroupPeopleSerializer, 409: WRONG_KIND})
    def get(self, request: Request, pk: int) -> Response:
        """200 with how many people the group holds now, and each of them.

        409 *This group's filters need fixing.* while a stored filter is refused.
        """
        try:
            payload = _people_payload(_group(pk))
        except groups.GroupFiltersError as broken:
            return refused(broken)
        return Response(GroupPeopleSerializer(payload).data)

    @extend_schema(
        request=GroupMemberAddSerializer,
        responses={201: GroupPersonSerializer, 409: WRONG_KIND},
    )
    def post(self, request: Request, pk: int) -> Response:
        """201 with the person, once a fixed group holds them.

        An account that is not a member or a friend, or is in the group already, is a
        400 keyed ``user``; a live group is a 409.
        """
        group = _group(pk)
        payload = GroupMemberAddSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            account = groups.add_member(group, payload.validated_data["user"])
        except DomainValidationError:
            raise
        except DomainError as error:
            return refused(error)
        person = groups.person_of(account)
        return Response(GroupPersonSerializer(person).data, status=status.HTTP_201_CREATED)


class GroupMemberView(APIView):
    """``DELETE /bulk-email/groups/{id}/members/{user_id}`` -- take one person out."""

    permission_classes = [IsManagement]

    @extend_schema(
        operation_id="bulk_email_groups_members_destroy",
        responses={204: None, 409: WRONG_KIND},
    )
    def delete(self, request: Request, pk: int, user_id: int) -> Response:
        """204 once the person is out of the fixed group; 404 when they were not in it."""
        group = _group(pk)
        try:
            groups.remove_member(group, user_id)
        except RecipientGroupMember.DoesNotExist as missing:
            raise Http404 from missing
        except DomainError as error:
            return refused(error)
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupPeopleCsvView(APIView):
    """``GET /bulk-email/groups/{id}/members.csv`` -- the people now, as a download."""

    permission_classes = [IsManagement]

    @extend_schema(responses=download_responses(CSV_MEDIA_TYPE, "One group's people."))
    def get(self, request: Request, pk: int) -> HttpResponse:
        """The CSV of everybody in the group now; 404 for an unknown group.

        409 *This group's filters need fixing.* while a stored filter is refused.
        """
        try:
            return report_response(groups.group_document(_group(pk)))
        except groups.GroupFiltersError as broken:
            return refused(broken)


class GroupFiltersView(APIView):
    """``POST /bulk-email/groups/{id}/filters`` -- add a filter set to a live group."""

    permission_classes = [IsManagement]

    @extend_schema(
        request=GroupFilterAddSerializer,
        responses={201: RecipientGroupFilterSerializer, 409: WRONG_KIND},
    )
    def post(self, request: Request, pk: int) -> Response:
        """201 with the filter set; a refused or repeated set is a 400 keyed ``filters``.

        A fixed group is a 409.
        """
        group = _group(pk)
        payload = GroupFilterAddSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            filter_set = groups.add_filter_set(group, payload.validated_data["filters"])
        except DomainValidationError:
            raise
        except DomainError as error:
            return refused(error)
        return Response(
            RecipientGroupFilterSerializer(filter_set).data, status=status.HTTP_201_CREATED
        )


class GroupFilterView(APIView):
    """``DELETE /bulk-email/groups/{id}/filters/{fid}`` -- take a filter set out."""

    permission_classes = [IsManagement]

    @extend_schema(
        operation_id="bulk_email_groups_filters_destroy",
        responses={204: None, 409: WRONG_KIND},
    )
    def delete(self, request: Request, pk: int, fid: int) -> Response:
        """204 once the set is gone; 404 for a set that is not the group's."""
        group = _group(pk)
        try:
            groups.remove_filter_set(group, fid)
        except RecipientGroupFilter.DoesNotExist as missing:
            raise Http404 from missing
        except DomainError as error:
            return refused(error)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PeopleSearchView(APIView):
    """``GET /bulk-email/groups/people?search=`` -- members and friends to add."""

    permission_classes = [IsManagement]

    @extend_schema(
        parameters=[OpenApiParameter("search", str, description="A name or an address.")],
        responses={200: PersonMatchSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        """200 with the first ten people the member list's search finds, by surname."""
        found = groups.people_matching(request.query_params.get("search", ""))
        return Response(PersonMatchSerializer(found, many=True).data)


class AddGroupView(APIView):
    """``POST /bulk-email/{id}/batch/add-group`` -- add a saved group to the batch."""

    permission_classes = [IsManagement]

    @extend_schema(
        request=AddGroupSerializer,
        responses={200: BulkEmailAddResultSerializer, 409: CONFLICT},
    )
    def post(self, request: Request, pk: int) -> Response:
        """200 with how many joined, how many were there already, and the batch's size.

        An unknown group, or a live one whose filters need fixing, is a 400 keyed
        ``group``.  A queued email goes back to a draft; one that has started sending is
        a 409.
        """
        bulk = email_for(request, pk)
        payload = AddGroupSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            result = groups.add_group(
                bulk, payload.validated_data["group"], actor=acting_user(request)
            )
        except DomainValidationError:
            raise
        except DomainError as error:
            return refused(error)
        return Response(BulkEmailAddResultSerializer(result).data)


class SaveGroupView(APIView):
    """``POST /bulk-email/{id}/save-group`` -- save the batch as a group."""

    permission_classes = [IsManagement]

    @extend_schema(request=SaveGroupSerializer, responses={201: RecipientGroupSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """201 with the group: the batch's people (fixed) or its filters (live).

        A taken name is a 400 keyed ``name``; an empty batch, or a live group from a
        batch with people no filters chose, a 400 keyed ``batch``.
        """
        bulk = email_for(request, pk)
        payload = SaveGroupSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        group = groups.save_group(
            bulk,
            name=payload.validated_data["name"],
            kind=payload.validated_data["kind"],
            actor=acting_user(request),
        )
        return Response(
            RecipientGroupSerializer(_group(group.pk)).data, status=status.HTTP_201_CREATED
        )
