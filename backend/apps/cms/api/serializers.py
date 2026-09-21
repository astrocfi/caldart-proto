"""Serializers for the site configuration endpoint.

``GET /api/v1/site/config`` builds its body from the Wagtail settings and the
page tree rather than from a model row, so these serializers describe the plain
dictionaries the view assembles.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

#: The two kinds of top-navigation entry: a Wagtail page, or a portal action.
NAV_KINDS = ("page", "portal")


class NavEntrySerializer(serializers.Serializer[dict[str, Any]]):
    """One top-navigation entry, as the public site and the portal both show it."""

    title = serializers.CharField()
    url = serializers.CharField()
    active = serializers.BooleanField()
    kind = serializers.ChoiceField(choices=NAV_KINDS)


class MembersPageSerializer(serializers.Serializer[dict[str, str]]):
    """One live members-only page, listed for callers who may open it."""

    title = serializers.CharField()
    url = serializers.CharField()


class SiteConfigSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /site/config`` — the chrome the portal needs before it has a user."""

    org_name = serializers.CharField()
    theme = serializers.CharField()
    contact_email = serializers.CharField(allow_blank=True)
    nav = NavEntrySerializer(many=True)
    members_pages = MembersPageSerializer(many=True)
