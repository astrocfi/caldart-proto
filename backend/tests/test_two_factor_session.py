"""The session side of two-factor sign-in: the middleware, and the admins' login routes.

A signed-in session of an account that needs a second factor, without the mark the code
step leaves, is signed out (``MfaSessionMiddleware``).  The Wagtail and Django admins
sign in through the portal: their login routes redirect there, carrying a local
``next`` and dropping anything else.
"""

from __future__ import annotations

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts import mfa
from apps.accounts.models import User
from apps.accounts.roles import MEMBER, TREASURER, USER_ADMIN, WEBSITE_ADMIN
from apps.accounts.status import clear_password_and_end_sessions
from tests.conftest import CHANGE_URL, GOOD_PASSWORD, ME_URL, without_second_factor
from tests.factories import DEFAULT_PASSWORD, UserFactory, confirmed_device

pytestmark = pytest.mark.django_db

LOGOUT_URL = "/api/v1/auth/logout"
PORTAL_LOGIN = "/portal/login"


@pytest.fixture
def admin() -> User:
    """A user administrator, whose role requires a second factor."""
    return UserFactory(roles=[MEMBER, USER_ADMIN])


# -- the middleware ----------------------------------------------------------


def test_a_staff_session_without_the_mark_is_signed_out(api_client: APIClient, admin: User) -> None:
    """A session from before two-factor sign-in has to sign in again."""
    api_client.force_login(admin)
    without_second_factor(api_client)
    assert api_client.get(ME_URL).status_code == 401


def test_a_signed_out_session_stays_signed_out(api_client: APIClient, admin: User) -> None:
    """The session is ended, not merely refused once."""
    api_client.force_login(admin)
    without_second_factor(api_client)
    api_client.get(ME_URL)
    assert api_client.session.get("_auth_user_id") is None


def test_a_marked_staff_session_is_kept(api_client: APIClient, admin: User) -> None:
    """A session that passed the code step goes on as before."""
    api_client.force_login(admin)
    assert api_client.get(ME_URL).status_code == 200


def test_a_member_without_two_factor_needs_no_mark(api_client: APIClient, member: User) -> None:
    """Nothing changes for an account that needs no second factor."""
    api_client.force_login(member)
    without_second_factor(api_client)
    assert api_client.get(ME_URL).status_code == 200


def test_a_member_with_a_device_needs_the_mark(api_client: APIClient, member: User) -> None:
    """Turning it on voluntarily asks every session for the second factor."""
    confirmed_device(member)
    api_client.force_login(member)
    without_second_factor(api_client)
    assert api_client.get(ME_URL).status_code == 401


def test_a_role_granted_mid_session_ends_the_session(api_client: APIClient, member: User) -> None:
    """Becoming a treasurer asks the next request for the second factor."""
    api_client.force_login(member)
    without_second_factor(api_client)
    member.add_role(TREASURER)
    assert api_client.get(ME_URL).status_code == 401


def test_a_mark_for_another_account_does_not_count(api_client: APIClient, admin: User) -> None:
    """The mark names the account that passed the code step."""
    api_client.force_login(admin)
    session = api_client.session
    session[mfa.VERIFIED_SESSION_KEY] = {"user": str(admin.pk + 1000), "at": 0}
    session.save()
    assert api_client.get(ME_URL).status_code == 401


def test_signing_out_works_for_a_session_owing_the_code(api_client: APIClient, admin: User) -> None:
    """Logout answers as always."""
    api_client.force_login(admin)
    without_second_factor(api_client)
    assert api_client.post(LOGOUT_URL).status_code == 204


def test_the_mark_survives_a_password_change(api_client: APIClient, admin: User) -> None:
    """Changing your password keeps you signed in, second factor and all."""
    api_client.force_login(admin)
    api_client.post(
        CHANGE_URL,
        {"current_password": DEFAULT_PASSWORD, "new_password": GOOD_PASSWORD},
        format="json",
    )
    assert api_client.get(ME_URL).status_code == 200


def test_an_admin_session_owing_the_code_is_sent_to_sign_in(client: Client) -> None:
    """A Wagtail admin session without the mark is signed out and sent to the portal."""
    editor = UserFactory(roles=[MEMBER, WEBSITE_ADMIN], is_staff=True)
    client.force_login(editor)
    without_second_factor(client)
    response = client.get("/admin/")
    assert response["Location"] == f"{PORTAL_LOGIN}?next=/admin/"


def test_the_site_pages_serve_an_owing_session_anonymous(client: Client, admin: User) -> None:
    """A path outside the API carries on, signed out, rather than failing."""
    client.force_login(admin)
    without_second_factor(client)
    assert client.get("/portal/login").status_code == 200


# -- the admins' login routes ------------------------------------------------


@pytest.mark.parametrize(
    ("url", "next_"),
    [("/admin/login/", "/admin/pages/"), ("/django-admin/login/", "/django-admin/")],
    ids=["wagtail", "django"],
)
def test_an_admin_login_route_sends_the_reader_to_the_portal(
    client: Client, url: str, next_: str
) -> None:
    """The portal's sign-in carries the admin page to return to."""
    response = client.get(url, {"next": next_})
    assert response["Location"] == f"{PORTAL_LOGIN}?next={next_}"


@pytest.mark.parametrize(
    "next_",
    ["https://evil.example/", "//evil.example/", "/\\evil.example/", "admin/", "javascript:x"],
    ids=["absolute", "scheme-relative", "backslash", "relative", "script"],
)
@pytest.mark.parametrize("url", ["/admin/login/", "/django-admin/login/"])
def test_an_unsafe_next_is_dropped(client: Client, url: str, next_: str) -> None:
    """Only a path on this site rides along to the portal."""
    assert client.get(url, {"next": next_})["Location"] == PORTAL_LOGIN


def test_an_admin_login_route_without_next_opens_the_portal_sign_in(client: Client) -> None:
    """No ``next`` is invented."""
    assert client.get("/admin/login/")["Location"] == PORTAL_LOGIN


@pytest.mark.parametrize("url", ["/admin/login/", "/django-admin/login/"])
def test_posting_credentials_to_an_admin_login_signs_nobody_in(
    client: Client, admin: User, url: str
) -> None:
    """The routes serve no form: a password posted there starts no session."""
    client.post(url, {"username": admin.email, "password": DEFAULT_PASSWORD})
    assert client.session.get("_auth_user_id") is None


def test_the_wagtail_admin_sends_a_signed_out_reader_to_the_portal(client: Client) -> None:
    """``WAGTAILADMIN_LOGIN_URL`` is the portal's sign-in."""
    assert client.get("/admin/")["Location"] == f"{PORTAL_LOGIN}?next=/admin/"


def test_the_django_admin_sends_a_signed_out_reader_to_the_portal(client: Client) -> None:
    """The Django admin's login route redirects on to the portal with the page."""
    first = client.get("/django-admin/")
    assert client.get(first["Location"])["Location"] == f"{PORTAL_LOGIN}?next=/django-admin/"


def test_the_public_sites_login_sends_the_reader_to_the_portal(client: Client) -> None:
    """Wagtail's private-page login is not served; the portal signs everybody in."""
    response = client.get("/_util/login/", {"next": "/members/"})
    assert response["Location"] == f"{PORTAL_LOGIN}?next=/members/"


def test_the_public_sites_login_takes_no_password(client: Client, member: User) -> None:
    """A password posted there signs nobody in."""
    client.post("/_util/login/", {"username": member.email, "password": DEFAULT_PASSWORD})
    assert client.session.get("_auth_user_id") is None


def test_the_django_admins_password_change_is_the_portals(client: Client, admin: User) -> None:
    """Every password is changed under the portal's rules."""
    client.force_login(admin)
    assert client.get("/django-admin/password_change/")["Location"] == "/portal/change-password"


def test_ending_an_accounts_sessions_takes_the_mark_with_them(
    api_client: APIClient, admin: User
) -> None:
    """Undoing a change of address ends every session, mark and all."""
    api_client.force_login(admin)
    key = api_client.session.session_key
    clear_password_and_end_sessions(admin)
    assert SessionStore(session_key=key).get(mfa.VERIFIED_SESSION_KEY) is None
    assert api_client.get(ME_URL).status_code == 401
