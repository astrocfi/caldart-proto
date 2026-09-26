"""Year-end contribution statements: who gets one, and the yearly send.

Every active account -- a member, a friend, or a donor -- that made at least one
settled contribution in a calendar year is sent one email,
``contribution_statement``, with that year's statement PDF attached
(:func:`apps.payments.receipts.render_statement_pdf`).  A
:class:`~apps.payments.models.YearStatement` row is written for each address
reached, so a rerun of :func:`send_year_statements` -- the yearly timer runs it
once, and an operator can run it again from the System screen -- sends nothing
twice.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from django.db.models import Model, Q
from django.utils import timezone

from apps.accounts.models import AccountKind, User
from apps.payments import receipts
from apps.payments.models import Payment, PaymentProvider, YearStatement
from apps.payments.reports import RECEIVED_STATUSES
from caldart import audit
from caldart.mail import send_templated
from caldart.org import org_details
from caldart.receipts import CONTRIBUTIONS_NOTICE
from caldart.reports import PDF_MEDIA_TYPE, money_label
from caldart.runs import RunAction, action_lines

log = logging.getLogger(__name__)

#: The subject of the statement email, in the house voice.
STATEMENT_SUBJECT = "{org}: your {year} contribution statement"

#: The kind an emailed statement is recorded under in a run's actions.
STATEMENT_KIND = "contribution_statement"


def givers_in_year(year: int) -> list[User]:
    """Every active account with a settled contribution in ``year``, by name.

    Any kind of account counts -- a member, a friend, or a donor -- as long as
    it is active; a deactivated account is never written to.  A contribution
    counts in the year of its ledger date, :attr:`~apps.payments.models.Payment.paid_on`
    expressed in SQL rather than :mod:`apps.payments.reports`'s ``paid_date``:
    the two agree for almost every payment, but ``paid_date`` falls back to
    ``created_at`` when ``completed_at`` is unset, which would pick a giver
    :func:`apps.payments.receipts.contribution_payments` and
    :func:`apps.payments.receipts.statement_years` do not agree is one, leaving
    them a statement of nothing.  Ordered by display name, so a live run and
    its dry-run rehearsal list the same givers in the same order.
    """
    manual_this_year = Q(provider=PaymentProvider.MANUAL, received_on__year=year)
    settled_this_year = ~Q(provider=PaymentProvider.MANUAL) & Q(completed_at__year=year)
    user_ids = (
        Payment.objects.filter(
            status__in=RECEIVED_STATUSES, contribution_cents__gt=0, user__is_active=True
        )
        .filter(manual_this_year | settled_this_year)
        .values_list("user_id", flat=True)
        .distinct()
    )
    return list(User.objects.filter(pk__in=user_ids).order_by("last_name", "first_name", "pk"))


@dataclass
class StatementRun:
    """Structured summary of one run of the year-end statement sender.

    Printed by ``manage.py send_year_statements`` and answered by ``POST
    /system/statements/run`` as ``{year, sent, skipped, failed, actions}``.
    ``sent`` is every account newly emailed, ``skipped`` every account that
    already held a :class:`~apps.payments.models.YearStatement` for the year,
    and ``failed`` every one the mail server refused or that had no address on
    file.  ``actions`` names the accounts behind ``sent``, one
    :class:`~caldart.runs.RunAction` each, carrying the year's net total as
    ``amount_cents``.
    """

    year: int
    today: date
    dry_run: bool
    sent: int = 0
    skipped: int = 0
    failed: int = 0
    actions: list[RunAction] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """The counts and the actions ``POST /system/statements/run`` answers with."""
        return {
            "year": self.year,
            "sent": self.sent,
            "skipped": self.skipped,
            "failed": self.failed,
            "actions": [action.as_dict() for action in self.actions],
        }

    def as_lines(self) -> list[str]:
        """Human-readable summary, one fact per line, then one line per action."""
        lines = [
            f"year             {self.year}",
            f"today            {self.today.isoformat()}",
            f"mode             {'dry run (nothing sent)' if self.dry_run else 'live'}",
            f"sent             {self.sent}",
            f"skipped          {self.skipped}",
            f"failed           {self.failed}",
        ]
        return lines + action_lines(self.actions, dry_run=self.dry_run)


def _net_total_cents(user: User, year: int) -> int:
    """``user``'s net giving in ``year``: every settled contribution, less refunds."""
    data = receipts.statement_data(user, year)
    return sum(line.amount_cents - line.refunded_cents for line in data.contributions)


def _statement_context(user: User, year: int, total_cents: int) -> dict[str, object]:
    """The template context :func:`_send_statement` renders both bodies with."""
    org = org_details()
    return {
        "org_name": org.name,
        "contact_email": org.contact_email,
        "first_name": user.first_name or user.display_name,
        "year": year,
        "total": money_label(total_cents),
        "notice": CONTRIBUTIONS_NOTICE,
        "payments_url": receipts.payments_url(),
        "is_donor": user.kind == AccountKind.DONOR,
    }


def _send_statement(user: User, year: int, total_cents: int) -> bool | None:
    """Email ``user``'s ``year`` statement and claim it, or say why it did not go.

    Claims the :class:`~apps.payments.models.YearStatement` row with
    ``get_or_create`` before sending anything: Django resolves two callers
    racing for the same row through the unique constraint, so of two runs
    started at once -- the timer and an operator's click on the System screen,
    say -- only one wins the claim.  Answers ``None`` without sending anything
    when another run already holds the claim, ``False`` without writing
    anything for an account with no address on file, and ``False`` (releasing
    the claim, so the next run tries again) for one a mail server refuses (an
    ``OSError``); every ``False`` is logged.  Answers ``True`` once the email is
    confirmed sent.
    """
    if not user.email:
        log.warning("No address on file for account %s; no %s statement sent", user.pk, year)
        return False
    claim, claimed = YearStatement.objects.get_or_create(
        user=user, year=year, defaults={"sent_at": timezone.now()}
    )
    if not claimed:
        log.info(
            "Contribution statement for account %s, %s already claimed by another run",
            user.pk,
            year,
        )
        return None
    try:
        send_templated(
            to=user.email,
            subject=STATEMENT_SUBJECT.format(org=org_details().name, year=year),
            template="contribution_statement",
            context=_statement_context(user, year, total_cents),
            attachments=[
                (
                    receipts.statement_filename(user, year),
                    receipts.render_statement_pdf(user, year),
                    PDF_MEDIA_TYPE,
                )
            ],
            user_id=user.pk,
        )
    except OSError as exc:
        log.error(
            "Contribution statement for account %s, %s could not be sent: %s", user.pk, year, exc
        )
        claim.delete()
        return False
    return True


def send_year_statements(
    year: int,
    *,
    today: date | None = None,
    dry_run: bool = False,
    actor: Model | str = audit.COMMAND_ACTOR,
) -> StatementRun:
    """Email every active giver's ``year`` statement, and say who got one.

    ``today`` is only for the run's own record; the year and the givers in it
    are fixed by ``year``.  A giver who already holds a
    :class:`~apps.payments.models.YearStatement` for ``year`` is skipped: a
    rerun for a year already sent reaches nobody again, and so is one claimed
    between this run's start and its own send by a second run started at the
    same time.  A dry run writes and emails nothing, and reports exactly the
    accounts and totals a live run would reach: an account with no address on
    file is counted in ``failed``, precisely as a live run would count it.

    Nothing about one account stops the run: an address that fails, or one
    with no address at all, is counted in ``failed`` and the walk carries on.
    Every run ends with one ``statements.run`` audit record carrying the year,
    the mode and the counts.
    """
    day = timezone.localdate() if today is None else today
    run = StatementRun(year=year, today=day, dry_run=dry_run)
    already_sent = set(YearStatement.objects.filter(year=year).values_list("user_id", flat=True))
    for user in givers_in_year(year):
        if user.pk in already_sent:
            run.skipped += 1
            continue
        total_cents = _net_total_cents(user, year)
        outcome = bool(user.email) if dry_run else _send_statement(user, year, total_cents)
        if outcome is None:
            run.skipped += 1
        elif outcome:
            run.sent += 1
            run.actions.append(
                RunAction(
                    kind=STATEMENT_KIND,
                    member=user.display_name,
                    email=user.email,
                    amount_cents=total_cents,
                )
            )
        else:
            run.failed += 1

    audit.record(
        audit.STATEMENTS_RUN,
        actor=actor,
        dry_run=dry_run,
        year=year,
        sent=run.sent,
        skipped=run.skipped,
        failed=run.failed,
    )
    return run
