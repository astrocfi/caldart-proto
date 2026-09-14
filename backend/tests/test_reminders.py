"""The renewal reminder scanner.

Every kind fires on exactly its offset and nowhere near it, a second run sends
nothing, a dry run writes nothing, and members who have already renewed —
including lifetime members — are left alone.
"""

from __future__ import annotations

from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from freezegun import freeze_time

from apps.members.models import MembershipStatusChoices
from apps.reminders.models import REMINDER_OFFSETS, ReminderKind, ReminderLog
from apps.reminders.services import ReminderRun, renew_url, send_renewal_reminders
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

TODAY = date(2026, 6, 15)

ALL_KINDS = [
    ReminderKind.T60,
    ReminderKind.T30,
    ReminderKind.T7,
    ReminderKind.EXPIRED,
    ReminderKind.POST30,
]


def ends_on_for(kind: str, today: date = TODAY) -> date:
    """The expiry date that puts a member in ``kind``'s cohort."""
    return today - timedelta(days=REMINDER_OFFSETS[kind])


def make_member(plan, ends_on: date | None, *, email: str | None = None, **user_kwargs):
    """A user with one term ending on ``ends_on`` (``None`` for lifetime)."""
    if email is not None:
        user_kwargs["email"] = email
    user = UserFactory(**user_kwargs)
    starts_on = (ends_on - timedelta(days=364)) if ends_on else TODAY - timedelta(days=30)
    membership = MembershipFactory(user=user, plan=plan, starts_on=starts_on, ends_on=ends_on)
    return user, membership


# --------------------------------------------------------------------- kinds
@pytest.mark.parametrize("kind", ALL_KINDS)
def test_each_kind_fires_on_its_own_offset(annual_plan, mailoutbox, kind):
    user, membership = make_member(annual_plan, ends_on_for(kind))

    run = send_renewal_reminders(today=TODAY)

    assert run.sent == 1
    assert run.sent_by_kind == {kind: 1}
    assert len(mailoutbox) == 1
    log = ReminderLog.objects.get()
    assert (log.user, log.membership, log.kind) == (user, membership, kind)
    assert log.to_email == user.email


@pytest.mark.parametrize("kind", ALL_KINDS)
@pytest.mark.parametrize("slip", [-1, 1])
def test_nothing_fires_a_day_either_side(annual_plan, mailoutbox, kind, slip):
    make_member(annual_plan, ends_on_for(kind) + timedelta(days=slip))

    run = send_renewal_reminders(today=TODAY)

    assert (run.sent, len(mailoutbox)) == (0, 0)


def test_every_cohort_in_one_pass(annual_plan, mailoutbox):
    for kind in ALL_KINDS:
        make_member(annual_plan, ends_on_for(kind), email=f"{kind}@example.test")

    run = send_renewal_reminders(today=TODAY)

    assert run.sent == 5
    assert run.sent_by_kind == dict.fromkeys(ALL_KINDS, 1)
    assert sorted(m.to[0] for m in mailoutbox) == sorted(f"{k}@example.test" for k in ALL_KINDS)


# --------------------------------------------------------------------- dedupe
def test_a_second_run_the_same_day_sends_nothing(annual_plan, mailoutbox):
    make_member(annual_plan, ends_on_for(ReminderKind.T30))

    send_renewal_reminders(today=TODAY)
    again = send_renewal_reminders(today=TODAY)

    assert again.sent == 0
    assert again.skipped_by_reason == {"already_sent": 1}
    assert len(mailoutbox) == 1
    assert ReminderLog.objects.count() == 1


def test_a_later_kind_still_fires_after_an_earlier_one(annual_plan, mailoutbox):
    user, membership = make_member(annual_plan, ends_on_for(ReminderKind.T30))

    send_renewal_reminders(today=TODAY)
    # 23 days later the same term is a week from expiry.
    send_renewal_reminders(today=TODAY + timedelta(days=23))

    assert sorted(ReminderLog.objects.values_list("kind", flat=True)) == ["t30", "t7"]
    assert len(mailoutbox) == 2


# --------------------------------------------------------------------- expiry
def test_lapsed_terms_are_flipped_to_expired(annual_plan):
    _user, membership = make_member(annual_plan, TODAY - timedelta(days=1))

    run = send_renewal_reminders(today=TODAY)

    membership.refresh_from_db()
    assert membership.status == MembershipStatusChoices.EXPIRED
    assert run.expired_flipped == 1


def test_a_term_ending_today_is_not_yet_expired(annual_plan):
    _user, membership = make_member(annual_plan, TODAY)

    run = send_renewal_reminders(today=TODAY)

    membership.refresh_from_db()
    assert membership.status == MembershipStatusChoices.ACTIVE
    assert run.expired_flipped == 0
    assert run.sent_by_kind == {ReminderKind.EXPIRED: 1}


# -------------------------------------------------------------------- dry run
def test_dry_run_writes_nothing(annual_plan, mailoutbox):
    make_member(annual_plan, ends_on_for(ReminderKind.T7), email="soon@example.test")
    _user, lapsed = make_member(annual_plan, TODAY - timedelta(days=1), email="gone@example.test")

    run = send_renewal_reminders(today=TODAY, dry_run=True)

    assert run.dry_run is True
    assert run.sent == 1
    assert run.expired_flipped == 1
    assert mailoutbox == []
    assert ReminderLog.objects.count() == 0
    lapsed.refresh_from_db()
    assert lapsed.status == MembershipStatusChoices.ACTIVE


def test_a_dry_run_does_not_suppress_the_real_one(annual_plan, mailoutbox):
    make_member(annual_plan, ends_on_for(ReminderKind.T60))

    send_renewal_reminders(today=TODAY, dry_run=True)
    run = send_renewal_reminders(today=TODAY)

    assert run.sent == 1
    assert len(mailoutbox) == 1


# ---------------------------------------------------------------------- skips
def test_lifetime_members_are_skipped(annual_plan, life_plan, mailoutbox):
    user, _annual = make_member(annual_plan, ends_on_for(ReminderKind.T30))
    MembershipFactory(user=user, plan=life_plan, starts_on=TODAY, ends_on=None)

    run = send_renewal_reminders(today=TODAY)

    assert run.sent == 0
    assert run.skipped_by_reason == {"lifetime": 1}
    assert mailoutbox == []


def test_deactivated_users_are_skipped(annual_plan, mailoutbox):
    make_member(annual_plan, ends_on_for(ReminderKind.T7), is_active=False)

    run = send_renewal_reminders(today=TODAY)

    assert run.skipped_by_reason == {"inactive_user": 1}
    assert mailoutbox == []


def test_a_user_without_an_email_address_is_skipped(annual_plan, mailoutbox):
    make_member(annual_plan, ends_on_for(ReminderKind.T7), email="")

    run = send_renewal_reminders(today=TODAY)

    assert run.skipped_by_reason == {"no_email": 1}
    assert mailoutbox == []


def test_a_member_who_renewed_early_is_skipped(annual_plan, mailoutbox):
    """Back-to-back terms mean coverage runs past this term's ``ends_on``."""
    expiring = ends_on_for(ReminderKind.T30)
    user, _term = make_member(annual_plan, expiring)
    MembershipFactory(
        user=user,
        plan=annual_plan,
        starts_on=expiring + timedelta(days=1),
        ends_on=expiring + timedelta(days=365),
    )

    run = send_renewal_reminders(today=TODAY)

    assert run.sent == 0
    assert run.skipped_by_reason == {"renewed": 1}
    assert mailoutbox == []


def test_post30_is_skipped_once_the_member_has_rejoined(annual_plan, mailoutbox):
    user, _lapsed = make_member(annual_plan, ends_on_for(ReminderKind.POST30))
    MembershipFactory(
        user=user, plan=annual_plan, starts_on=TODAY, ends_on=TODAY + timedelta(days=364)
    )

    run = send_renewal_reminders(today=TODAY)

    assert run.skipped_by_reason == {"renewed": 1}
    assert mailoutbox == []


def test_cancelled_terms_are_ignored_entirely(annual_plan, mailoutbox):
    _user, membership = make_member(annual_plan, ends_on_for(ReminderKind.T30))
    membership.status = MembershipStatusChoices.CANCELLED
    membership.save(update_fields=["status"])

    run = send_renewal_reminders(today=TODAY)

    assert (run.sent, run.skipped, len(mailoutbox)) == (0, 0, 0)


# ---------------------------------------------------------------------- email
def test_email_content(annual_plan, mailoutbox, settings, site_settings):
    settings.SITE_URL = "https://caldart.example.org/"
    site_settings.org_name = "The California DART Network"
    site_settings.contact_email = "info@caldart.example.org"
    site_settings.save()

    user, _membership = make_member(annual_plan, ends_on_for(ReminderKind.T30))
    user.first_name = "Marta"
    user.save(update_fields=["first_name"])

    send_renewal_reminders(today=TODAY)

    message = mailoutbox[0]
    assert message.subject == "The California DART Network: your membership expires in 30 days"
    assert message.to == [user.email]
    assert message.from_email == settings.DEFAULT_FROM_EMAIL

    text = message.body
    assert "Hello Marta," in text
    assert "https://caldart.example.org/portal/renew" in text
    assert "Annual" in text
    assert "info@caldart.example.org" in text

    (html, mime) = message.alternatives[0]
    assert mime == "text/html"
    assert "https://caldart.example.org/portal/renew" in html
    assert "The California DART Network" in html
    assert "<!doctype html>" in html


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_every_kind_renders_both_bodies(annual_plan, mailoutbox, kind):
    make_member(annual_plan, ends_on_for(kind))

    send_renewal_reminders(today=TODAY)

    message = mailoutbox[0]
    assert message.body.strip()
    assert renew_url() in message.body
    assert renew_url() in message.alternatives[0][0]


def test_renew_url_follows_site_url(settings):
    settings.SITE_URL = "https://example.test/"
    assert renew_url() == "https://example.test/portal/renew"


# -------------------------------------------------------------------- command
# Noon UTC is mid-morning in America/Los_Angeles, so the local date is the one
# named here rather than the day before.
@freeze_time("2026-06-15 12:00:00")
def test_the_scan_defaults_to_today(annual_plan, mailoutbox):
    make_member(annual_plan, ends_on_for(ReminderKind.T7))

    run = send_renewal_reminders()

    assert run.today == TODAY
    assert len(mailoutbox) == 1


def test_command_sends_and_reports(annual_plan, mailoutbox):
    make_member(annual_plan, ends_on_for(ReminderKind.T30, date(2026, 6, 15)))
    out = StringIO()

    call_command("send_renewal_reminders", "--today=2026-06-15", stdout=out)

    output = out.getvalue()
    assert "today            2026-06-15" in output
    assert "mode             live" in output
    assert "sent 1, skipped 0" in output
    assert len(mailoutbox) == 1


def test_command_dry_run_says_so(annual_plan, mailoutbox):
    make_member(annual_plan, ends_on_for(ReminderKind.T30, date(2026, 6, 15)))
    out = StringIO()

    call_command("send_renewal_reminders", "--today=2026-06-15", "--dry-run", stdout=out)

    assert "dry run (nothing written)" in out.getvalue()
    assert "would send 1, skipped 0" in out.getvalue()
    assert mailoutbox == []


def test_command_rejects_a_bad_date(annual_plan):
    with pytest.raises(CommandError, match="--today must be YYYY-MM-DD"):
        call_command("send_renewal_reminders", "--today=last tuesday")


def test_summary_lines_cover_every_kind():
    run = ReminderRun(today=TODAY, dry_run=False)
    run.record_sent(ReminderKind.T7)
    run.record_skipped("lifetime")

    lines = "\n".join(run.as_lines())

    for kind in ALL_KINDS:
        assert kind in lines
    assert "lifetime" in lines
    assert run.as_dict() == {"sent": 1, "skipped": 1}
