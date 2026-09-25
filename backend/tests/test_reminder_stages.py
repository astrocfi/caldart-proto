"""The five reminder stages, day by day.

Each kind is a stage: a span of expiry dates, not a single date.  The first
table walks every expiry date from seventy days before a scan to seventy days
after it and names the one stage, if any, that a term ending that day is in.
The rest drive the scanner over the same spans, so a member who joins the
register between two stages still gets the one they are in.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.mail import EmailMessage, EmailMultiAlternatives

from apps.members.models import Membership, MembershipPlan
from apps.reminders.models import ReminderKind
from apps.reminders.services import KIND_ORDER, send_renewal_reminders, stage_span
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

#: The day every scan in this module is run on.
TODAY = date(2026, 6, 15)


def term_ending(
    plan: MembershipPlan, days_from_today: int, *, email: str | None = None
) -> Membership:
    """One member holding a term that ends ``days_from_today`` days from :data:`TODAY`."""
    ends_on = TODAY + timedelta(days=days_from_today)
    user = UserFactory() if email is None else UserFactory(email=email)
    return MembershipFactory(
        user=user, plan=plan, starts_on=ends_on - timedelta(days=364), ends_on=ends_on
    )


def stage_of(days_from_today: int) -> str | None:
    """The kind whose stage covers a term ending ``days_from_today`` days from the scan.

    ``None`` when no stage covers that day.  Fails if two stages claim it, which
    would mean one scan sending a member two reminders.
    """
    ends_on = TODAY + timedelta(days=days_from_today)
    covering = []
    for kind in KIND_ORDER:
        earliest, latest = stage_span(kind, TODAY)
        if earliest <= ends_on <= latest:
            covering.append(kind)
    assert len(covering) <= 1, f"{ends_on} is in more than one stage: {covering}"
    return covering[0] if covering else None


def expected_stage(days_from_today: int) -> str | None:
    """The stage a term ending ``days_from_today`` days from the scan belongs in."""
    if 31 <= days_from_today <= 60:
        return ReminderKind.T60
    if 8 <= days_from_today <= 30:
        return ReminderKind.T30
    if 1 <= days_from_today <= 7:
        return ReminderKind.T7
    if -6 <= days_from_today <= 0:
        return ReminderKind.EXPIRED
    if -60 <= days_from_today <= -30:
        return ReminderKind.POST30
    return None


# --------------------------------------------------------------------- spans
@pytest.mark.parametrize("days_from_today", range(-70, 71))
def test_every_expiry_date_is_in_exactly_the_stage_it_belongs_to(days_from_today: int) -> None:
    """Every day from seventy before the scan to seventy after names its own stage."""
    assert stage_of(days_from_today) == expected_stage(days_from_today)


@pytest.mark.parametrize(
    ("kind", "first", "last"),
    [
        (ReminderKind.T60, 31, 60),
        (ReminderKind.T30, 8, 30),
        (ReminderKind.T7, 1, 7),
        (ReminderKind.EXPIRED, -6, 0),
        (ReminderKind.POST30, -60, -30),
    ],
)
def test_each_stage_spans_the_days_it_covers(kind: str, first: int, last: int) -> None:
    """``stage_span`` returns the inclusive first and last expiry date of the stage."""
    assert stage_span(kind, TODAY) == (
        TODAY + timedelta(days=first),
        TODAY + timedelta(days=last),
    )


# ------------------------------------------------------------------- scanning
@pytest.mark.parametrize(
    ("days_from_today", "kind"),
    [
        (60, ReminderKind.T60),
        (45, ReminderKind.T60),
        (31, ReminderKind.T60),
        (30, ReminderKind.T30),
        (23, ReminderKind.T30),
        (8, ReminderKind.T30),
        (7, ReminderKind.T7),
        (3, ReminderKind.T7),
        (1, ReminderKind.T7),
        (0, ReminderKind.EXPIRED),
        (-3, ReminderKind.EXPIRED),
        (-6, ReminderKind.EXPIRED),
        (-30, ReminderKind.POST30),
        (-45, ReminderKind.POST30),
        (-60, ReminderKind.POST30),
    ],
)
def test_the_scan_sends_the_stage_the_span_names(
    annual_plan: MembershipPlan,
    mailoutbox: list[EmailMessage],
    days_from_today: int,
    kind: str,
) -> None:
    """A term ending inside a stage's span is sent that stage's email."""
    term_ending(annual_plan, days_from_today)

    run = send_renewal_reminders(today=TODAY)

    assert run.sent_by_kind == {kind: 1}


@pytest.mark.parametrize("days_from_today", [-70, -61, -29, -7, 61, 90])
def test_the_scan_sends_nothing_between_the_stages(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage], days_from_today: int
) -> None:
    """A term ending on a day no stage covers is left alone."""
    term_ending(annual_plan, days_from_today)

    run = send_renewal_reminders(today=TODAY)

    assert run.sent == 0


def test_a_member_twenty_three_days_out_gets_this_stage_and_the_next(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A term 23 days out is in ``t30`` today and in ``t7`` sixteen days later."""
    term_ending(annual_plan, 23)

    first = send_renewal_reminders(today=TODAY)
    second = send_renewal_reminders(today=TODAY + timedelta(days=16))

    assert first.sent_by_kind == {ReminderKind.T30: 1}
    assert second.sent_by_kind == {ReminderKind.T7: 1}


def test_a_member_three_days_out_gets_only_the_last_call(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A term three days from expiry is past ``t60`` and ``t30``, so only ``t7`` goes."""
    term_ending(annual_plan, 3)

    run = send_renewal_reminders(today=TODAY)

    assert run.sent_by_kind == {ReminderKind.T7: 1}


def test_a_stage_is_sent_once_however_long_the_term_sits_in_it(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A term inside one stage for several days is sent that stage's email once."""
    term_ending(annual_plan, 30)

    for day in range(5):
        send_renewal_reminders(today=TODAY + timedelta(days=day))

    assert len(mailoutbox) == 1


def test_one_scan_reaches_a_whole_stage_of_members(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """Every member inside ``t30``'s span is written to by the same scan."""
    for days in range(8, 31):
        term_ending(annual_plan, days, email=f"in{days}@example.test")

    run = send_renewal_reminders(today=TODAY)

    assert run.sent_by_kind == {ReminderKind.T30: 23}


# ------------------------------------------------------- the expired wording
def test_the_expired_email_says_today_on_the_expiry_day(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A term running out on the day of the scan is told today is its last day."""
    term_ending(annual_plan, 0)

    send_renewal_reminders(today=TODAY)

    assert mailoutbox[0].subject.endswith("your membership expires today")


def test_the_expired_body_says_today_on_the_expiry_day(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """The body of an on-the-day ``expired`` email speaks of tomorrow, not the past."""
    term_ending(annual_plan, 0)

    send_renewal_reminders(today=TODAY)

    assert "From tomorrow it reads as expired" in mailoutbox[0].body


def test_the_expired_subject_counts_the_days_since_the_term_ran_out(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A term that ran out three days ago is told so, rather than "expires today"."""
    term_ending(annual_plan, -3)

    send_renewal_reminders(today=TODAY)

    assert mailoutbox[0].subject.endswith("your membership expired 3 days ago")


def test_the_expired_body_counts_the_days_since_the_term_ran_out(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """The body of a late ``expired`` email states the same day count as its subject."""
    term_ending(annual_plan, -3)

    send_renewal_reminders(today=TODAY)

    assert "3 days ago" in mailoutbox[0].body


def test_the_expired_body_says_one_day_in_the_singular(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A term that ran out yesterday reads "1 day ago", not "1 days ago"."""
    term_ending(annual_plan, -1)

    send_renewal_reminders(today=TODAY)

    assert "1 day ago" in mailoutbox[0].body


def test_the_expired_html_alternative_follows_the_text_body(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """The HTML alternative of a late ``expired`` email also says it has expired."""
    term_ending(annual_plan, -4)

    send_renewal_reminders(today=TODAY)

    message = mailoutbox[0]
    assert isinstance(message, EmailMultiAlternatives)
    (html, _mime) = message.alternatives[0]
    assert isinstance(html, str)
    assert "Your membership has expired" in html


def test_a_term_ending_tomorrow_is_told_one_day_in_the_singular(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """The first day of the ``t7`` stage reads "1 day", not "1 days"."""
    term_ending(annual_plan, 1)

    send_renewal_reminders(today=TODAY)

    assert mailoutbox[0].subject.endswith("your membership expires in 1 day")


def test_a_term_ending_tomorrow_says_one_day_in_its_body(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """The ``t7`` body pluralizes its day count the same way its subject does."""
    term_ending(annual_plan, 1)

    send_renewal_reminders(today=TODAY)

    assert "1 day left" in mailoutbox[0].body
