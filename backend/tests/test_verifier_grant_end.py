"""A verifier grant that ends on a date.

Whoever grants the verifier role, on the member check or the user record, may give it
a last day (``User.verifier_until``).  The role works through that day; after it,
``User.roles`` leaves ``verifier`` out, so every permission check, a signed-in session
included, stops honoring it.  The contract is ``docs/developer/api-aircraft.rst`` and
``docs/developer/api-auth.rst``.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import MEMBER, VERIFIER
from apps.accounts.services import set_verifier
from caldart import audit
from caldart.dates import format_display_date
from caldart.exceptions import DomainValidationError
from tests.conftest import audit_messages, read_csv
from tests.factories import AircraftFactory, MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db

USERS_URL = "/api/v1/admin/users"


def _today() -> date:
    """Today, in the site's time zone."""
    return timezone.localdate()


def _grant_url(user: User) -> str:
    """The member check's grant endpoint for ``user``."""
    return f"/api/v1/leader/members/{user.pk}/verifier"


@pytest.fixture
def pilot(db: None) -> User:
    """A plain member with a profile, who doesn't hold the verifier role."""
    user = UserFactory(email="pilot@example.test", roles=[MEMBER])
    MemberProfileFactory(user=user)
    return user


@pytest.fixture
def lapsed_verifier(pilot: User) -> User:
    """``pilot``, granted the verifier role through yesterday."""
    pilot.add_role(VERIFIER)
    pilot.verifier_until = _today() - timedelta(days=1)
    pilot.save(update_fields=["verifier_until"])
    return pilot


@pytest.fixture
def leader_client(api_client: APIClient, dart_leader: User) -> APIClient:
    """A client signed in as the ``dart_leader`` fixture."""
    api_client.force_login(dart_leader)
    return api_client


# -- the grant ----------------------------------------------------------------


def test_a_grant_from_the_member_check_stores_its_last_day(
    leader_client: APIClient, pilot: User
) -> None:
    """``until`` is answered on the status card as ``verifier_until``."""
    until = _today() + timedelta(days=3)
    response = leader_client.put(
        _grant_url(pilot), {"verifier": True, "until": until.isoformat()}, format="json"
    )
    assert response.json()["verifier_until"] == until.isoformat()


def test_a_grant_without_an_end_answers_null(leader_client: APIClient, pilot: User) -> None:
    """A grant without ``until`` doesn't end."""
    response = leader_client.put(_grant_url(pilot), {"verifier": True}, format="json")
    assert response.json()["verifier_until"] is None


def test_a_last_day_before_today_is_refused(leader_client: APIClient, pilot: User) -> None:
    """A grant can't end before it starts: 400 under ``verifier_until``."""
    yesterday = _today() - timedelta(days=1)
    response = leader_client.put(
        _grant_url(pilot), {"verifier": True, "until": yesterday.isoformat()}, format="json"
    )
    assert (response.status_code, response.json()) == (
        400,
        {"verifier_until": ["Choose today or a later day."]},
    )


def test_a_grant_may_end_today(dart_leader: User, pilot: User) -> None:
    """Today is the earliest last day, and the role works through it."""
    set_verifier(dart_leader, pilot, wanted=True, until=_today())
    pilot.refresh_from_db()
    assert pilot.roles == [MEMBER, VERIFIER]


def test_a_refused_last_day_does_not_grant_the_role(dart_leader: User, pilot: User) -> None:
    """Nothing is written when the last day is refused."""
    with pytest.raises(DomainValidationError, match="Choose today or a later day"):
        set_verifier(dart_leader, pilot, wanted=True, until=_today() - timedelta(days=1))
    pilot.refresh_from_db()
    assert pilot.roles == [MEMBER]


def test_the_grant_and_its_last_day_are_audited_together(
    dart_leader: User, pilot: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """The ``account.roles`` line carries the last day."""
    until = _today() + timedelta(days=3)
    set_verifier(dart_leader, pilot, wanted=True, until=until)
    assert audit_messages(audit_log) == [
        f"action={audit.ACCOUNT_ROLES} actor={dart_leader.pk} target={pilot.pk} "
        f"added=verifier removed=- verifier_until={until.isoformat()}"
    ]


def test_granting_again_extends_a_grant(
    dart_leader: User, pilot: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """A second grant without an end makes the role permanent, audited as an update."""
    set_verifier(dart_leader, pilot, wanted=True, until=_today() + timedelta(days=3))
    audit_log.clear()
    set_verifier(dart_leader, pilot, wanted=True)
    assert audit_messages(audit_log) == [
        f"action={audit.ACCOUNT_UPDATE} actor={dart_leader.pk} target={pilot.pk} "
        "fields=verifier_until verifier_until=none"
    ]


def test_taking_the_role_away_clears_its_last_day(dart_leader: User, pilot: User) -> None:
    """A revoked grant doesn't keep a last day."""
    set_verifier(dart_leader, pilot, wanted=True, until=_today() + timedelta(days=3))
    set_verifier(dart_leader, pilot, wanted=False)
    pilot.refresh_from_db()
    assert pilot.verifier_until is None


# -- after the last day -------------------------------------------------------


def test_the_role_stops_after_its_last_day(lapsed_verifier: User) -> None:
    """``roles`` leaves ``verifier`` out once its last day has passed."""
    assert lapsed_verifier.roles == [MEMBER]


def test_a_signed_in_lapsed_verifier_cannot_verify(
    api_client: APIClient, lapsed_verifier: User
) -> None:
    """The aircraft check refuses a verifier whose grant has ended, 403."""
    api_client.force_login(lapsed_verifier)
    aircraft = AircraftFactory()
    response = api_client.put(
        f"/api/v1/leader/aircraft/{aircraft.pk}/verification", {"verified": False}, format="json"
    )
    assert response.status_code == 403


def test_the_status_card_reads_a_lapsed_verifier_as_not_one(
    leader_client: APIClient, lapsed_verifier: User
) -> None:
    """The member check offers to make a lapsed verifier a verifier again."""
    body = leader_client.get(f"/api/v1/leader/members/{lapsed_verifier.pk}/status").json()
    assert (body["is_verifier"], body["verifier_until"]) == (False, None)


def test_the_role_filter_leaves_out_a_lapsed_verifier(
    api_client: APIClient, user_admin: User, lapsed_verifier: User, verifier: User
) -> None:
    """``?role=verifier`` on the users list keeps only the grants still working."""
    api_client.force_login(user_admin)
    rows = api_client.get(USERS_URL, {"role": VERIFIER}).json()["results"]
    assert [row["id"] for row in rows] == [verifier.pk]


# -- the user record ----------------------------------------------------------


def test_the_user_record_grants_the_role_with_a_last_day(
    api_client: APIClient, user_admin: User, pilot: User
) -> None:
    """``PUT /admin/users/{id}`` writes the roles and the last day together."""
    api_client.force_login(user_admin)
    until = _today() + timedelta(days=10)
    response = api_client.patch(
        f"{USERS_URL}/{pilot.pk}",
        {"roles": [MEMBER, VERIFIER], "verifier_until": until.isoformat()},
        format="json",
    )
    assert (response.json()["roles"], response.json()["verifier_until"]) == (
        [MEMBER, VERIFIER],
        until.isoformat(),
    )


def test_the_user_record_does_not_keep_a_last_day_without_the_role(
    api_client: APIClient, user_admin: User, pilot: User
) -> None:
    """A last day sent for an account that isn't a verifier isn't saved."""
    api_client.force_login(user_admin)
    until = _today() + timedelta(days=10)
    response = api_client.patch(
        f"{USERS_URL}/{pilot.pk}", {"verifier_until": until.isoformat()}, format="json"
    )
    assert response.json()["verifier_until"] is None


# -- the roles report ---------------------------------------------------------


def test_the_roles_report_names_the_last_day_of_a_grant(
    account_admin_client: APIClient, dart_leader: User, pilot: User
) -> None:
    """A verifier whose grant ends reads ``Verifier until`` the day in the Role column."""
    until = _today() + timedelta(days=10)
    set_verifier(dart_leader, pilot, wanted=True, until=until)
    table = read_csv(
        account_admin_client.get(
            "/api/v1/reports/roles/export.csv", {"role": VERIFIER, "columns": "role,email"}
        )
    )
    assert table == [
        ["Role", "Email"],
        [f"Verifier until {format_display_date(until)}", "pilot@example.test"],
    ]
