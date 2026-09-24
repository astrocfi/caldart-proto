"""``manage.py seed_facts`` -- the JSON document the end-to-end specs read."""

import json
from datetime import date, timedelta
from typing import Any

import pytest
from django.core.management import call_command

from apps.accounts.seed import DEMO_ACCOUNTS, DEMO_PASSWORD
from apps.members.models import MembershipPlan
from tests.factories import (
    AircraftFactory,
    MemberProfileFactory,
    MembershipFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


def read_facts(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    """Run ``seed_facts`` and parse the JSON document it writes to stdout."""
    call_command("seed_facts")
    parsed: dict[str, Any] = json.loads(capsys.readouterr().out)
    return parsed


def test_reports_the_shared_demo_password(capsys: pytest.CaptureFixture[str]) -> None:
    """``demoPassword`` is the password every seeded demo account shares."""
    assert read_facts(capsys)["demoPassword"] == DEMO_PASSWORD


def test_reports_every_demo_account_by_key(capsys: pytest.CaptureFixture[str]) -> None:
    """``accounts`` maps each demo key to the address the seed gives that account."""
    expected = {key: email for key, email, *_rest in DEMO_ACCOUNTS}
    assert read_facts(capsys)["accounts"] == expected


def test_reports_the_plan_prices_in_cents(
    annual_plan: MembershipPlan,
    life_plan: MembershipPlan,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``planPricesCents`` maps each plan slug to its price in cents."""
    assert read_facts(capsys)["planPricesCents"] == {"annual": 4_500, "life": 65_000}


def test_reports_no_plan_prices_when_no_plan_is_seeded(
    db: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """``planPricesCents`` is empty when the database holds no membership plan."""
    assert read_facts(capsys)["planPricesCents"] == {}


def test_writes_one_json_object_and_nothing_else(capsys: pytest.CaptureFixture[str]) -> None:
    """The command writes exactly the five documented keys, and no other output."""
    call_command("seed_facts")
    captured = capsys.readouterr()
    assert captured.err == ""
    assert sorted(json.loads(captured.out)) == [
        "accounts",
        "demoPassword",
        "leaderCheck",
        "manualPaymentCount",
        "planPricesCents",
    ]


def test_names_a_member_for_each_leader_check_case(
    capsys: pytest.CaptureFixture[str], annual_plan: MembershipPlan, today: date
) -> None:
    """``leaderCheck`` finds an insured pilot, a lapsed policy and a lapsed member."""
    day = timedelta(days=1)
    insured = UserFactory(email="insured@example.test", first_name="Ivy", last_name="North")
    MemberProfileFactory(user=insured).aircraft.add(
        AircraftFactory(n_number="N111AA", insurance_expiration=today + 200 * day)
    )
    MembershipFactory(user=insured, plan=annual_plan, starts_on=today - day)

    lapsed_cover = UserFactory(email="cover@example.test", first_name="Ola", last_name="South")
    MemberProfileFactory(user=lapsed_cover).aircraft.add(
        AircraftFactory(n_number="N222BB", insurance_expiration=today - 10 * day)
    )
    MembershipFactory(user=lapsed_cover, plan=annual_plan, starts_on=today - day)

    lapsed_member = UserFactory(email="lapsed@example.test", first_name="Eli", last_name="West")
    MemberProfileFactory(user=lapsed_member)

    facts = read_facts(capsys)["leaderCheck"]

    assert facts["insuredPilot"] == {"name": "Ivy North", "nNumber": "N111AA"}
    assert facts["lapsedInsurance"] == {"name": "Ola South", "nNumber": "N222BB"}
    assert facts["expiredMember"]["name"] == "Eli West"


def test_a_plane_with_no_policy_on_file_is_not_a_lapsed_policy(
    capsys: pytest.CaptureFixture[str], annual_plan: MembershipPlan, today: date
) -> None:
    """``lapsedInsurance`` needs an expiration date in the past, not a blank one.

    An airframe with nothing on file reads as "No insurance on file" in the portal,
    not as expired cover, so naming its owner would send the leader-check spec
    looking for words that are not on the screen.
    """
    day = timedelta(days=1)
    nothing_on_file = UserFactory(email="blank@example.test", first_name="Ada", last_name="Ames")
    MemberProfileFactory(user=nothing_on_file).aircraft.add(
        AircraftFactory(n_number="N333CC", insurance_expiration=None)
    )
    MembershipFactory(user=nothing_on_file, plan=annual_plan, starts_on=today - day)

    lapsed_cover = UserFactory(email="cover@example.test", first_name="Ola", last_name="South")
    MemberProfileFactory(user=lapsed_cover).aircraft.add(
        AircraftFactory(n_number="N222BB", insurance_expiration=today - 10 * day)
    )
    MembershipFactory(user=lapsed_cover, plan=annual_plan, starts_on=today - day)

    facts = read_facts(capsys)["leaderCheck"]

    assert facts["lapsedInsurance"] == {"name": "Ola South", "nNumber": "N222BB"}
