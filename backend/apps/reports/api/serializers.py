"""Serializers for the report endpoints."""

from __future__ import annotations

from typing import TypedDict

from rest_framework import serializers


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
