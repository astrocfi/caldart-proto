"""``manage.py seed_facts`` -- the JSON document the end-to-end specs read."""

import json
from datetime import date, timedelta
from typing import Any

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import AccountKind, User
from apps.accounts.seed import DEMO_ACCOUNTS, DEMO_PASSWORD
from apps.aircraft.models import Aircraft, Registration, RegistryImport
from apps.aircraft.registry import FIXTURE_DIR, import_registry
from apps.members.models import MembershipPlan
from apps.members.verification import ITEMS
from apps.payments.models import PaymentStatus
from tests.factories import (
    AircraftFactory,
    MemberProfileFactory,
    MembershipFactory,
    PaymentFactory,
    RenewalMandateFactory,
    UserFactory,
    expire_membership,
)

pytestmark = pytest.mark.django_db

#: The columns that mark all three of a person's items verified: an insured pilot is
#: only a GO when they are.
VERIFIED_PROFILE: dict[str, Any] = {f"{item.slug}_verified_at": timezone.now() for item in ITEMS}

#: The column that marks an aircraft's insurance verified.
VERIFIED_INSURANCE: dict[str, Any] = {"insurance_verified_at": timezone.now()}


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
    """The command writes exactly the documented keys, and no other output."""
    call_command("seed_facts")
    captured = capsys.readouterr()
    assert captured.err == ""
    assert sorted(json.loads(captured.out)) == [
        "accounts",
        "autoRenewal",
        "demoPassword",
        "leaderCheck",
        "manualPaymentCount",
        "planPricesCents",
        "refundedPayment",
        "registry",
    ]


def test_names_a_member_for_each_leader_check_case(
    capsys: pytest.CaptureFixture[str], annual_plan: MembershipPlan, today: date
) -> None:
    """``leaderCheck`` finds an insured pilot, a lapsed policy and a lapsed member."""
    day = timedelta(days=1)
    insured = UserFactory(email="insured@example.test", first_name="Ivy", last_name="North")
    MemberProfileFactory(user=insured, **VERIFIED_PROFILE).aircraft.add(
        AircraftFactory(
            n_number="N111AA", insurance_expiration=today + 200 * day, **VERIFIED_INSURANCE
        )
    )
    MembershipFactory(user=insured, plan=annual_plan, starts_on=today - day)

    lapsed_cover = UserFactory(email="cover@example.test", first_name="Ola", last_name="South")
    MemberProfileFactory(user=lapsed_cover).aircraft.add(
        AircraftFactory(n_number="N222BB", insurance_expiration=today - 10 * day)
    )
    MembershipFactory(user=lapsed_cover, plan=annual_plan, starts_on=today - day)

    # Somebody who never joined, and a friend, come first by name and are not lapsed.
    MemberProfileFactory(
        user=UserFactory(email="never@example.test", first_name="Ada", last_name="Ames")
    )
    MemberProfileFactory(
        user=UserFactory(
            email="pal@example.test", first_name="Bo", last_name="Bell", kind=AccountKind.FRIEND
        )
    )
    lapsed_member = UserFactory(email="lapsed@example.test", first_name="Eli", last_name="West")
    MemberProfileFactory(user=lapsed_member)
    expire_membership(lapsed_member, annual_plan)

    facts = read_facts(capsys)["leaderCheck"]

    assert facts["insuredPilot"] == {"name": "Ivy North", "nNumber": "N111AA"}
    assert facts["lapsedInsurance"] == {"name": "Ola South", "nNumber": "N222BB"}
    assert facts["expiredMember"]["name"] == "Eli West"


def test_an_insured_pilot_holds_no_policy_inside_the_warning_window(
    capsys: pytest.CaptureFixture[str], annual_plan: MembershipPlan, today: date
) -> None:
    """``insuredPilot`` skips a member one of whose policies runs out within 30 days.

    The portal calls such a policy "Expiring soon" rather than "Insured", which is
    not the card the spec is looking for.
    """
    day = timedelta(days=1)
    soon = UserFactory(email="soon@example.test", first_name="Al", last_name="Able")
    MemberProfileFactory(user=soon, **VERIFIED_PROFILE).aircraft.add(
        AircraftFactory(
            n_number="N444DD", insurance_expiration=today + 200 * day, **VERIFIED_INSURANCE
        ),
        AircraftFactory(
            n_number="N555EE", insurance_expiration=today + 10 * day, **VERIFIED_INSURANCE
        ),
    )
    MembershipFactory(user=soon, plan=annual_plan, starts_on=today - day)
    steady = UserFactory(email="steady@example.test", first_name="Bea", last_name="Best")
    MemberProfileFactory(user=steady, **VERIFIED_PROFILE).aircraft.add(
        AircraftFactory(
            n_number="N666FF", insurance_expiration=today + 200 * day, **VERIFIED_INSURANCE
        )
    )
    MembershipFactory(user=steady, plan=annual_plan, starts_on=today - day)

    facts = read_facts(capsys)["leaderCheck"]

    assert facts["insuredPilot"] == {"name": "Bea Best", "nNumber": "N666FF"}


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


def test_names_the_member_whose_payment_came_back(
    member: User, capsys: pytest.CaptureFixture[str]
) -> None:
    """``refundedPayment`` names the partially refunded payment and who made it."""
    payment = PaymentFactory(
        user=member, status=PaymentStatus.PARTIALLY_REFUNDED, amount_cents=4_500
    )

    facts = read_facts(capsys)["refundedPayment"]

    assert facts["email"] == member.email
    assert facts["receiptNumber"] == payment.receipt_number


def test_reports_no_refunded_payment_when_nothing_came_back(
    db: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """``refundedPayment`` carries empty strings when the seed refunded nothing."""
    assert read_facts(capsys)["refundedPayment"]["receiptNumber"] == ""


def test_names_an_active_mandate_whose_charge_is_still_ahead(
    capsys: pytest.CaptureFixture[str], today: date
) -> None:
    """``autoRenewal.activeMandate`` skips a mandate charged today or already overdue.

    A renewal spec that reads this member expects nothing to charge yet, so a
    mandate the daily scan would already be acting on is the wrong one to hand it.
    """
    day = timedelta(days=1)
    RenewalMandateFactory(next_charge_on=today - day)
    RenewalMandateFactory(next_charge_on=today)
    ahead = RenewalMandateFactory(next_charge_on=today + 30 * day)

    facts = read_facts(capsys)["autoRenewal"]["activeMandate"]

    assert facts["email"] == ahead.user.email


def test_reports_no_active_mandate_when_every_charge_is_due_or_overdue(
    db: None, today: date, capsys: pytest.CaptureFixture[str]
) -> None:
    """``autoRenewal.activeMandate`` is empty when nothing is far enough out."""
    RenewalMandateFactory(next_charge_on=today)

    facts = read_facts(capsys)["autoRenewal"]["activeMandate"]

    assert facts == {"name": "", "email": "", "methodLabel": ""}


def test_an_insured_pilot_is_verified_on_every_count(
    capsys: pytest.CaptureFixture[str], annual_plan: MembershipPlan, today: date
) -> None:
    """``insuredPilot`` skips a member whose documents or airplane are not verified."""
    day = timedelta(days=1)
    for email, first, profile_stamps, insurance_stamps in (
        ("papers@example.test", "Al", {}, VERIFIED_INSURANCE),
        ("plane@example.test", "Bo", VERIFIED_PROFILE, {}),
        ("both@example.test", "Cy", VERIFIED_PROFILE, VERIFIED_INSURANCE),
    ):
        user = UserFactory(email=email, first_name=first, last_name="Able")
        MemberProfileFactory(user=user, **profile_stamps).aircraft.add(
            AircraftFactory(insurance_expiration=today + 200 * day, **insurance_stamps)
        )
        MembershipFactory(user=user, plan=annual_plan, starts_on=today - day)

    facts = read_facts(capsys)["leaderCheck"]

    assert facts["insuredPilot"]["name"] == "Cy Able"


def test_names_a_current_pilot_with_nothing_verified(
    capsys: pytest.CaptureFixture[str], annual_plan: MembershipPlan, today: date
) -> None:
    """``unverifiedPilot`` is current, medically current, and has nothing verified."""
    day = timedelta(days=1)
    verified = UserFactory(email="done@example.test", first_name="Ann", last_name="Adams")
    MemberProfileFactory(user=verified, **VERIFIED_PROFILE)
    MembershipFactory(user=verified, plan=annual_plan, starts_on=today - day)
    pending = UserFactory(email="pending@example.test", first_name="Ben", last_name="Brown")
    MemberProfileFactory(user=pending)
    MembershipFactory(user=pending, plan=annual_plan, starts_on=today - day)

    facts = read_facts(capsys)["leaderCheck"]

    assert facts["unverifiedPilot"] == {"name": "Ben Brown"}


# -- the registry ---------------------------------------------------------------------


@pytest.fixture
def registry() -> None:
    """The fixture registry, imported as the seed imports it."""
    import_registry(str(FIXTURE_DIR))


def test_names_a_registered_n_number_not_on_the_register(
    registry: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """``registry.knownNNumber`` is in the registry and on no register record."""
    known = read_facts(capsys)["registry"]["knownNNumber"]
    assert (
        Registration.objects.filter(n_number=known).exists(),
        Aircraft.objects.filter(n_number=known).exists(),
    ) == (True, False)


def test_skips_a_registered_n_number_already_on_the_register(
    registry: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """An N-number the register already holds is never the one named."""
    first = read_facts(capsys)["registry"]["knownNNumber"]
    AircraftFactory(n_number=first)
    assert read_facts(capsys)["registry"]["knownNNumber"] != first


def test_describes_the_known_registration(
    registry: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """``knownType`` and ``knownYear`` are what a lookup on ``knownNNumber`` answers."""
    facts = read_facts(capsys)["registry"]
    registration = Registration.objects.get(n_number=facts["knownNNumber"])
    assert (facts["knownType"], facts["knownYear"], facts["knownOwner"]) == (
        str(registration.type),
        registration.year,
        registration.registrant_name,
    )


def test_reports_the_date_the_registry_is_as_of(
    registry: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """``registry.asOf`` is the newest successful import's day, written ``MM/DD/YYYY``."""
    finished = RegistryImport.objects.get().finished_at
    assert finished is not None
    expected = timezone.localtime(finished).strftime("%m/%d/%Y")
    assert read_facts(capsys)["registry"]["asOf"] == expected


def test_reports_no_registry_before_an_import(capsys: pytest.CaptureFixture[str]) -> None:
    """With nothing imported, the registry facts are empty."""
    assert read_facts(capsys)["registry"] == {
        "knownNNumber": "",
        "knownType": "",
        "knownYear": None,
        "knownOwner": "",
        "asOf": "",
    }
