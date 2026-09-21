"""``acting_user``: the account behind a members API request."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import NotAuthenticated
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.accounts.models import User
from apps.members.api.actors import acting_user


def test_it_returns_the_signed_in_account(member: User) -> None:
    """A request an authentication class resolved hands back that account."""
    request = Request(APIRequestFactory().get("/api/v1/me/profile"))
    request.user = member

    assert acting_user(request) == member


def test_it_refuses_an_anonymous_request() -> None:
    """An unauthenticated request raises the error the API renders as 401."""
    request = Request(APIRequestFactory().get("/api/v1/me/profile"))
    request.user = AnonymousUser()

    with pytest.raises(NotAuthenticated, match="Authentication credentials were not provided."):
        acting_user(request)
