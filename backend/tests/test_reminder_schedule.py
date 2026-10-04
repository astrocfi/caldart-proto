"""The editable reminder schedule: its rules, its endpoint, and what it moves.

``docs/developer/reminders.rst`` describes the schedule and the spans it gives each
stage, and ``docs/developer/api-system.rst`` the ``/admin/reminders/schedule``
endpoint.  A system administrator edits the four days; an account administrator reads
them.  Editing them moves the stages' spans and the words every screen prints for a
stage, and never sends a member a stage they already had.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN
from apps.mail import purposes
from apps.mail.purposes import (
    PURPOSE_LABELS,
    purpose_label,
    purpose_labels,
    register_purpose_labels,
)
from apps.members.models import Membership, MembershipPlan
from apps.reminders.models import ReminderKind, ReminderLog, ReminderSchedule, schedule_errors
from apps.reminders.services import ReminderRun, send_renewal_reminders, stage_span
from tests.conftest import read_csv, role_matrix
from tests.factories import EmailLogFactory, MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

SCHEDULE_URL = "/api/v1/admin/reminders/schedule"
EMAILS_URL = "/api/v1/system/emails"
PURPOSES_URL = "/api/v1/system/emails/purposes"
EMAILS_CSV_URL = "/api/v1/reports/emails/export.csv"

#: The day every scan in this module is run on.
TODAY = date(2026, 6, 15)

#: The schedule a fresh installation runs.
DEFAULTS: dict[str, int] = {
    "first_days_before": 60,
    "second_days_before": 30,
    "final_days_before": 7,
    "lapsed_days_after": 30,
}

#: An edited schedule every stage of which differs from the defaults.
EDITED: dict[str, int] = {
    "first_days_before": 45,
    "second_days_before": 20,
    "final_days_before": 3,
    "lapsed_days_after": 14,
}


def store(days: dict[str, int]) -> ReminderSchedule:
    """Save ``days`` as the stored schedule and return it."""
    schedule = ReminderSchedule.load()
    for name, value in days.items():
        setattr(schedule, name, value)
    schedule.save()
    return schedule


def body(**overrides: int) -> dict[str, int]:
    """A complete ``PUT`` body of the default days, with ``overrides`` merged in."""
    return {**DEFAULTS, **overrides}


def term_ending(plan: MembershipPlan, days_from_today: int) -> Membership:
    """One member holding a term that ends ``days_from_today`` days from :data:`TODAY`."""
    ends_on = TODAY + timedelta(days=days_from_today)
    return MembershipFactory(
        user=UserFactory(), plan=plan, starts_on=ends_on - timedelta(days=364), ends_on=ends_on
    )


# --------------------------------------------------------------------------
# The rules
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("overrides", "field", "message"),
    [
        (
            {"first_days_before": 181},
            "first_days_before",
            "The first reminder can be at most 180 days before expiry.",
        ),
        (
            {"first_days_before": 30},
            "first_days_before",
            "The first reminder must be more days before expiry than the second.",
        ),
        (
            {"second_days_before": 7},
            "second_days_before",
            "The second reminder must be more days before expiry than the final one.",
        ),
        (
            {"final_days_before": 0},
            "final_days_before",
            "The final reminder must be at least 1 day before expiry.",
        ),
        (
            {"lapsed_days_after": 6},
            "lapsed_days_after",
            "The lapsed reminder must be 7 to 365 days after expiry.",
        ),
        (
            {"lapsed_days_after": 366},
            "lapsed_days_after",
            "The lapsed reminder must be 7 to 365 days after expiry.",
        ),
    ],
    ids=[
        "first-over-180",
        "first-not-above-second",
        "second-not-above-final",
        "final-under-1",
        "lapsed-under-7",
        "lapsed-over-365",
    ],
)
def test_a_schedule_outside_a_bound_is_refused_naming_the_field_and_the_rule(
    overrides: dict[str, int], field: str, message: str
) -> None:
    """Each broken rule is reported, in words, against the field it constrains."""
    assert schedule_errors(**body(**overrides)) == {field: message}


@pytest.mark.parametrize(
    "overrides",
    [
        {"first_days_before": 180},
        {"first_days_before": 31},
        {"second_days_before": 8},
        {"final_days_before": 1},
        {"lapsed_days_after": 7},
        {"lapsed_days_after": 365},
    ],
    ids=[
        "first-at-180",
        "first-one-above-second",
        "second-one-above-final",
        "final-at-1",
        "lapsed-at-7",
        "lapsed-at-365",
    ],
)
def test_a_schedule_on_a_bound_is_accepted(overrides: dict[str, int]) -> None:
    """The limit itself is inside every rule."""
    assert schedule_errors(**body(**overrides)) == {}


def test_every_broken_rule_is_reported_at_once() -> None:
    """A schedule breaking three rules hears about all three."""
    errors = schedule_errors(
        first_days_before=200, second_days_before=5, final_days_before=5, lapsed_days_after=1
    )

    assert set(errors) == {"first_days_before", "second_days_before", "lapsed_days_after"}


# --------------------------------------------------------------------------
# GET and PUT /admin/reminders/schedule
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_account_and_system_administrators_read_the_schedule(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Only ``account_admin`` and ``system_admin`` may read the schedule."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(SCHEDULE_URL).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_only_a_system_administrator_changes_the_schedule(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Every other role, an account administrator included, is refused the ``PUT``."""
    api_client.force_login(all_role_users[role])
    response = api_client.put(SCHEDULE_URL, EDITED, format="json")
    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize("method", ["get", "put"])
def test_the_schedule_needs_a_session(api_client: APIClient, method: str) -> None:
    """An anonymous caller is a 401 either way."""
    response = getattr(api_client, method)(SCHEDULE_URL, EDITED, format="json")
    assert response.status_code == 401


def test_the_defaults_apply_before_anyone_saves_a_schedule(
    system_admin_client: APIClient,
) -> None:
    """60, 30, 7 and 30 days, saved by nobody, at no time."""
    assert system_admin_client.get(SCHEDULE_URL).json() == {
        **DEFAULTS,
        "updated_by": None,
        "updated_at": None,
    }


def test_reading_the_schedule_writes_nothing(system_admin_client: APIClient) -> None:
    """The defaults are answered without storing a row."""
    system_admin_client.get(SCHEDULE_URL)
    assert ReminderSchedule.objects.count() == 0


def test_a_saved_schedule_is_answered_with_its_days(system_admin_client: APIClient) -> None:
    """The ``PUT`` answers the four days it stored."""
    response = system_admin_client.put(SCHEDULE_URL, EDITED, format="json")
    assert {name: response.json()[name] for name in EDITED} == EDITED


def test_a_saved_schedule_names_who_saved_it(
    system_admin_client: APIClient, system_admin: User
) -> None:
    """``updated_by`` is the saving administrator's display name."""
    response = system_admin_client.put(SCHEDULE_URL, EDITED, format="json")
    assert response.json()["updated_by"] == system_admin.display_name


def test_a_saved_schedule_says_when(system_admin_client: APIClient) -> None:
    """``updated_at`` is the stored row's own time."""
    response = system_admin_client.put(SCHEDULE_URL, EDITED, format="json")
    saved_at = datetime.fromisoformat(response.json()["updated_at"])
    assert saved_at == ReminderSchedule.load().updated_at


def test_the_saved_schedule_is_the_one_row(system_admin_client: APIClient) -> None:
    """Saving twice keeps one row, holding the second save's days."""
    system_admin_client.put(SCHEDULE_URL, EDITED, format="json")
    system_admin_client.put(SCHEDULE_URL, body(first_days_before=90), format="json")

    assert list(ReminderSchedule.objects.values_list("pk", "first_days_before")) == [(1, 90)]


def test_a_refused_schedule_answers_400_keyed_by_field(system_admin_client: APIClient) -> None:
    """The body names the field and the rule it breaks."""
    response = system_admin_client.put(SCHEDULE_URL, body(lapsed_days_after=3), format="json")

    assert response.status_code == 400
    assert response.json() == {
        "lapsed_days_after": ["The lapsed reminder must be 7 to 365 days after expiry."]
    }


def test_a_refused_schedule_changes_nothing(system_admin_client: APIClient) -> None:
    """The stored days stay as they were."""
    store(EDITED)
    system_admin_client.put(SCHEDULE_URL, body(final_days_before=0), format="json")

    assert ReminderSchedule.load().final_days_before == EDITED["final_days_before"]


@pytest.mark.parametrize("value", ["", "ten", None])
def test_a_day_that_is_not_a_whole_number_is_refused(
    system_admin_client: APIClient, value: str | None
) -> None:
    """A blank, a word or a null in a day field is a 400 against that field."""
    response = system_admin_client.put(
        SCHEDULE_URL, {**DEFAULTS, "final_days_before": value}, format="json"
    )
    assert list(response.json()) == ["final_days_before"]


# --------------------------------------------------------------------------
# The spans follow the schedule
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kind", "first", "last"),
    [
        (ReminderKind.FIRST, 21, 45),
        (ReminderKind.SECOND, 4, 20),
        (ReminderKind.FINAL, 1, 3),
        (ReminderKind.EXPIRED, -6, 0),
        (ReminderKind.LAPSED, -44, -14),
    ],
)
def test_an_edited_schedule_moves_the_spans(kind: str, first: int, last: int) -> None:
    """Each stage covers the days the stored schedule gives it, still tiling."""
    store(EDITED)
    assert stage_span(kind, TODAY) == (
        TODAY + timedelta(days=first),
        TODAY + timedelta(days=last),
    )


def test_a_given_schedule_wins_over_the_stored_one() -> None:
    """``stage_span`` reads the schedule it is handed rather than the stored one."""
    store(EDITED)
    assert stage_span(ReminderKind.FIRST, TODAY, schedule=ReminderSchedule()) == (
        TODAY + timedelta(days=31),
        TODAY + timedelta(days=60),
    )


def test_the_scan_sends_the_stage_the_edited_schedule_names(
    annual_plan: MembershipPlan,
) -> None:
    """A term 22 days out, in ``second`` on the defaults, is in ``first`` on 45/20/3."""
    store(EDITED)
    term_ending(annual_plan, 22)

    run = send_renewal_reminders(today=TODAY)

    assert run.sent_by_kind == {ReminderKind.FIRST: 1}


def send_first_then_second_then_restore(plan: MembershipPlan) -> ReminderRun:
    """Walk one term back into a stage it already had, and return the last scan.

    The term ends 35 days out, in ``first`` on the defaults, and is sent ``first``.
    A second reminder moved out to 40 days puts it in ``second`` the next day, and it
    is sent ``second``.  Moving the second reminder back to 30 days the day after puts
    the term, 33 days out, back in ``first``'s span.
    """
    term_ending(plan, 35)
    send_renewal_reminders(today=TODAY)
    store(body(second_days_before=40))
    send_renewal_reminders(today=TODAY + timedelta(days=1))
    store(body())
    return send_renewal_reminders(today=TODAY + timedelta(days=2))


def test_a_schedule_edit_that_moves_a_member_back_sends_nothing(
    annual_plan: MembershipPlan,
) -> None:
    """A member put back into ``first`` after having it is skipped as already sent."""
    run = send_first_then_second_then_restore(annual_plan)

    assert run.skipped_by_reason == {"already_sent": 1}


def test_a_schedule_edit_that_moves_a_member_back_writes_no_log_row(
    annual_plan: MembershipPlan,
) -> None:
    """The member's log holds one ``first`` row and one ``second`` row, and no more."""
    send_first_then_second_then_restore(annual_plan)

    kinds = sorted(ReminderLog.objects.values_list("kind", flat=True))
    assert kinds == [ReminderKind.FIRST, ReminderKind.SECOND]


@pytest.mark.parametrize(
    ("first", "second", "final", "lapsed"),
    [(3, 2, 1, 7), (180, 179, 178, 365), (180, 2, 1, 7), (100, 99, 1, 8), (60, 30, 7, 30)],
    ids=["tightest", "widest-before", "long-first", "long-second", "defaults"],
)
def test_the_spans_tile_without_a_gap_or_an_overlap(
    first: int, second: int, final: int, lapsed: int
) -> None:
    """Every expiry date is in exactly the one stage the schedule puts it in, or none."""
    schedule = ReminderSchedule(
        first_days_before=first,
        second_days_before=second,
        final_days_before=final,
        lapsed_days_after=lapsed,
    )
    expected_spans = {
        ReminderKind.FIRST: (second + 1, first),
        ReminderKind.SECOND: (final + 1, second),
        ReminderKind.FINAL: (1, final),
        ReminderKind.EXPIRED: (-6, 0),
        ReminderKind.LAPSED: (-(lapsed + 30), -lapsed),
    }
    mismatches = []
    for days_out in range(-(lapsed + 40), first + 10):
        ends_on = TODAY + timedelta(days=days_out)
        covering = [
            kind
            for kind in ReminderKind
            if stage_span(kind, TODAY, schedule=schedule)[0]
            <= ends_on
            <= stage_span(kind, TODAY, schedule=schedule)[1]
        ]
        expected = [kind for kind, (low, high) in expected_spans.items() if low <= days_out <= high]
        if covering != expected:
            mismatches.append((days_out, covering, expected))
    assert mismatches == []


# --------------------------------------------------------------------------
# The words follow the schedule
# --------------------------------------------------------------------------
def test_the_default_stages_read_as_their_days() -> None:
    """Each default stage reads by its one name and its day, 60 days out to 30 after."""
    assert ReminderSchedule().kind_labels() == {
        ReminderKind.FIRST: "First reminder (60 days before)",
        ReminderKind.SECOND: "Second reminder (30 days before)",
        ReminderKind.FINAL: "Final reminder (7 days before)",
        ReminderKind.EXPIRED: "Expired reminder (up to 6 days after)",
        ReminderKind.LAPSED: "Lapsed reminder (30 days after)",
    }


def test_a_final_reminder_one_day_out_reads_in_the_singular() -> None:
    """``1 day before``, not ``1 days``."""
    schedule = ReminderSchedule(final_days_before=1)
    assert schedule.kind_labels()[ReminderKind.FINAL] == "Final reminder (1 day before)"


def test_the_reminder_purposes_name_the_stored_days() -> None:
    """The email log's labels for the five reminders follow an edited schedule."""
    store(EDITED)
    assert [purpose_label(f"reminder_{kind}") for kind in ReminderKind] == [
        "First reminder (45 days before)",
        "Second reminder (20 days before)",
        "Final reminder (3 days before)",
        "Expired reminder (up to 6 days after)",
        "Lapsed reminder (14 days after)",
    ]


def test_the_purpose_filter_offers_the_stored_days_first(system_admin_client: APIClient) -> None:
    """The purpose filter leads with the reminders, worded from the stored schedule."""
    store(EDITED)

    labels = [row["label"] for row in system_admin_client.get(PURPOSES_URL).json()]

    assert labels[:2] == ["First reminder (45 days before)", "Second reminder (20 days before)"]


def test_an_email_log_row_names_the_stored_days(system_admin_client: APIClient) -> None:
    """A ``reminder_first`` row's ``purpose_label`` follows an edited schedule."""
    store(EDITED)
    EmailLogFactory(purpose="reminder_first")

    row = system_admin_client.get(EMAILS_URL).json()["results"][0]

    assert row["purpose_label"] == "First reminder (45 days before)"


def test_a_page_of_the_email_log_reads_the_schedule_once(
    system_admin_client: APIClient,
) -> None:
    """Labeling a page of reminder rows asks for the schedule one time, not per row."""
    EmailLogFactory.create_batch(3, purpose="reminder_first")

    with CaptureQueriesContext(connection) as queries:
        system_admin_client.get(EMAILS_URL)

    reads = [query for query in queries if "reminders_reminderschedule" in query["sql"]]
    assert len(reads) == 1


def test_the_email_log_report_names_the_stored_days(system_admin_client: APIClient) -> None:
    """The report's Purpose column follows an edited schedule."""
    store(EDITED)
    EmailLogFactory(purpose="reminder_lapsed")

    rows = read_csv(system_admin_client.get(EMAILS_CSV_URL))

    assert rows[1][rows[0].index("Purpose")] == "Lapsed reminder (14 days after)"


def test_a_registered_source_leads_the_purpose_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Labels from a registered source come before the fixed ones."""
    monkeypatch.setattr(purposes, "_label_sources", [])
    register_purpose_labels(lambda: {"board_minutes": "Board minutes"})

    assert list(purpose_labels()) == ["board_minutes", *PURPOSE_LABELS]


def test_registering_a_source_twice_registers_it_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same source is read once however often it is registered."""
    monkeypatch.setattr(purposes, "_label_sources", [])

    def source() -> dict[str, str]:
        """One label."""
        return {"board_minutes": "Board minutes"}

    register_purpose_labels(source)
    register_purpose_labels(source)

    assert purposes._label_sources == [source]
