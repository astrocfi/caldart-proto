"""What a scheduled scan did, person by person.

The renewal scan and the reminder scan both report counts, which answer "how
much happened" but never "to whom".  A :class:`RunAction` is one line of the
other answer: one email a scan sent, or one charge it took, named with the
member it concerned.  A dry run records exactly the actions a live run would
then carry out, so an operator can rehearse a scan and read off who it is about
to write to before letting it write to them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import TypedDict

from rest_framework import serializers

#: The action kind a charge is recorded under.  Every other kind is the name of
#: an email template or a reminder kind, and reads as "emailed <kind>".
CHARGE_KIND = "charge"


class RunActionDict(TypedDict):
    """One action as the run endpoints and the management commands serialize it."""

    kind: str
    member: str
    email: str
    on: str | None
    amount_cents: int | None
    detail: str


@dataclass(frozen=True)
class RunAction:
    """One email a scan sent, or one charge it took, and who it was about.

    ``kind`` names the email template or reminder kind, or :data:`CHARGE_KIND`
    for a charge.  ``member`` is the member's display name and ``email`` the
    address the message went to.  ``on`` is the date the action concerns -- the
    day a charge falls, or the day a term expires -- and is ``None`` when there
    is no such date.  ``amount_cents`` is what a charge comes to and is ``None``
    for an action that moves no money.  ``detail`` carries anything else worth
    printing, and is an empty string when there is nothing.
    """

    kind: str
    member: str
    email: str
    on: date | None = None
    amount_cents: int | None = None
    detail: str = ""

    def as_dict(self) -> RunActionDict:
        """The action as JSON, with ``on`` as an ISO ``YYYY-MM-DD`` string or null."""
        return {
            "kind": self.kind,
            "member": self.member,
            "email": self.email,
            "on": self.on.isoformat() if self.on is not None else None,
            "amount_cents": self.amount_cents,
            "detail": self.detail,
        }

    def as_line(self, *, dry_run: bool) -> str:
        """One printable line naming the member and what was, or would be, done.

        A charge reads ``would charge Dana Lee <dana@example.org> $45.00 on
        2026-06-19`` in a dry run and ``charged ...`` in a live one; every other
        kind reads ``would email renewal_notice to Dana Lee <dana@example.org>
        ...`` and ``emailed renewal_notice to ...``.  The amount, the date and
        the detail each appear only when the action carries one.
        """
        if self.kind == CHARGE_KIND:
            verb = "would charge" if dry_run else "charged"
        else:
            verb = f"would email {self.kind} to" if dry_run else f"emailed {self.kind} to"
        parts = [verb, f"{self.member} <{self.email}>"]
        if self.amount_cents is not None:
            parts.append(f"${self.amount_cents / 100:,.2f}")
        if self.on is not None:
            parts.append(f"on {self.on.isoformat()}")
        if self.detail:
            parts.append(f"({self.detail})")
        return " ".join(parts)


def action_lines(actions: Sequence[RunAction], *, dry_run: bool) -> list[str]:
    """Every action as a printable line, in the order the scan recorded them.

    An empty sequence gives an empty list, so a command that prints nothing
    after its counts is a scan that had nothing to do.
    """
    return [action.as_line(dry_run=dry_run) for action in actions]


class RunActionSerializer(serializers.Serializer[RunActionDict]):
    """One action a scan took, or would take, as the run endpoints answer it.

    ``kind`` is the email template or reminder kind, or ``charge``; ``on`` is an
    ISO date or null; ``amount_cents`` is integer cents or null.
    """

    kind = serializers.CharField()
    member = serializers.CharField()
    email = serializers.CharField()
    on = serializers.DateField(allow_null=True)
    amount_cents = serializers.IntegerField(allow_null=True)
    detail = serializers.CharField(allow_blank=True)
