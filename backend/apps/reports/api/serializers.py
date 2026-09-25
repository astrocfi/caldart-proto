"""Serializers for the report endpoints."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict

from rest_framework import serializers

from apps.reports.models import SavedColumnSet
from caldart.reports import FIXED_COLUMNS_MESSAGE, Report, select_columns

#: What a saved set with no columns is refused with.
NO_COLUMNS_MESSAGE = "Choose at least one column."


class ReportSummaryDict(TypedDict):
    """One report as ``GET /reports`` describes it."""

    slug: str
    title: str
    choosable: bool
    periods: bool


class ReportSummarySerializer(serializers.Serializer[ReportSummaryDict]):
    """One entry of ``GET /reports``: a report the caller may read.

    ``slug`` names it in every report URL, ``title`` labels it, ``choosable`` says
    whether ``?columns=`` may choose its columns, and ``periods`` whether it takes
    ``?period=``.
    """

    slug = serializers.CharField()
    title = serializers.CharField()
    choosable = serializers.BooleanField()
    periods = serializers.BooleanField()


def checked_columns(spec: Report, keys: Sequence[str]) -> list[str]:
    """``keys`` as a list, once ``spec``'s registry accepts them.

    An empty list is the report's default columns and always passes.  Any key at all
    for a report whose columns are fixed raises ``ValidationError`` reading
    :data:`~caldart.reports.FIXED_COLUMNS_MESSAGE`; an unknown or repeated key raises
    it with the message :func:`~caldart.reports.select_columns` gives, naming the key.
    """
    if len(keys) == 0:
        return []
    if not spec.choosable:
        raise serializers.ValidationError(FIXED_COLUMNS_MESSAGE)
    try:
        select_columns(spec.columns, keys)
    except ValueError as exc:
        raise serializers.ValidationError(str(exc)) from exc
    return list(keys)


class SavedColumnSetSerializer(serializers.ModelSerializer[SavedColumnSet]):
    """One saved set of a report's columns: ``{id, name, columns}``.

    Written with ``name`` (1 to 60 characters) and ``columns`` (the keys, in the order
    the report prints them).  The report is the one in the URL, handed in as the
    ``spec`` context entry; its registry must hold every key, no key may repeat, at
    least one is needed, and a report whose columns are fixed keeps no sets.
    """

    columns = serializers.ListField(child=serializers.CharField())

    class Meta:
        model = SavedColumnSet
        fields = ["id", "name", "columns"]
        read_only_fields = ["id"]

    def validate_columns(self, value: list[str]) -> list[str]:
        """The keys, once the report in the ``spec`` context entry accepts them."""
        spec: Report = self.context["spec"]
        if not spec.choosable:
            raise serializers.ValidationError(FIXED_COLUMNS_MESSAGE)
        if len(value) == 0:
            raise serializers.ValidationError(NO_COLUMNS_MESSAGE)
        return checked_columns(spec, value)
