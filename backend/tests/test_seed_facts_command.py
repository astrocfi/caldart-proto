"""``manage.py seed_facts`` -- the JSON document the end-to-end specs read."""

import json
from typing import Any

import pytest
from django.core.management import call_command

from apps.accounts.seed import DEMO_ACCOUNTS, DEMO_PASSWORD
from apps.members.models import MembershipPlan

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
    """The command writes exactly the three documented keys, and no other output."""
    call_command("seed_facts")
    captured = capsys.readouterr()
    assert captured.err == ""
    assert sorted(json.loads(captured.out)) == ["accounts", "demoPassword", "planPricesCents"]
