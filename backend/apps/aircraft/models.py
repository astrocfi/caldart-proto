"""Aircraft register with insurance data."""

from __future__ import annotations

import re
from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone

from caldart.models import TimestampedModel

_N_NUMBER_STRIP = re.compile(r"[^A-Za-z0-9]")

#: A US registration as the FAA issues them: ``N``, then one to five characters
#: that start with digits and may end with one or two letters, and never the
#: letters I or O, which read as 1 and 0.  ``N1``, ``N172SP`` and ``N9EL`` pass;
#: ``NA1``, ``N1234567`` and ``N1I`` do not.
N_NUMBER_RE = re.compile(r"^N[1-9][0-9]{0,3}[A-HJ-NP-Z]{0,2}$|^N[1-9][0-9]{0,4}$")

#: What an unusable registration is answered with, wherever it is typed.
N_NUMBER_MESSAGE = "Use a US registration like N172SP: N, then digits, then at most two letters."


def normalize_n_number(value: str | None) -> str:
    """Normalize a US registration to canonical ``N#####`` form.

    Upper-cased, punctuation and whitespace removed, and a leading ``N`` added
    when the caller left it off (``12345`` -> ``N12345``).  Non-US marks that
    already contain a hyphen keep their letters, e.g. ``c-gabc`` -> ``CGABC``.
    """
    if not value:
        return ""
    cleaned = _N_NUMBER_STRIP.sub("", value).upper()
    if not cleaned:
        return ""
    if cleaned[0].isdigit():
        cleaned = "N" + cleaned
    return cleaned


class OwnerType(models.TextChoices):
    """Who holds title to an aircraft on the register."""

    INDIVIDUAL = "individual", "Individual"
    FBO = "fbo", "FBO"
    CLUB = "club", "Flying club"


class Aircraft(TimestampedModel):
    """One airframe, with the insurance a DART leader needs to check."""

    n_number = models.CharField("N-number", max_length=12, unique=True)
    make = models.CharField(max_length=60, blank=True)
    model = models.CharField(max_length=60, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    owner_type = models.CharField(
        max_length=12, choices=OwnerType.choices, default=OwnerType.INDIVIDUAL
    )
    owner_name = models.CharField(max_length=160, blank=True)
    owner_contact = models.CharField(
        max_length=200, blank=True, help_text="Email or phone, free text."
    )
    seats = models.PositiveSmallIntegerField(null=True, blank=True)

    insurance_carrier = models.CharField(max_length=120, blank=True)
    insurance_policy_number = models.CharField(max_length=60, blank=True)
    insurance_liability_per_occurrence_cents = models.PositiveBigIntegerField(default=0)
    insurance_liability_per_person_cents = models.PositiveBigIntegerField(default=0)
    insurance_hull_cents = models.PositiveBigIntegerField(null=True, blank=True)
    insurance_expiration = models.DateField(null=True, blank=True)

    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aircraft_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aircraft_updated",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["n_number"]
        verbose_name = "aircraft"
        verbose_name_plural = "aircraft"
        indexes = [
            models.Index(fields=["insurance_expiration"], name="aircraft_insexp_idx"),
            models.Index(fields=["make", "model"], name="aircraft_make_model_idx"),
            models.Index(fields=["is_active"], name="aircraft_active_idx"),
        ]

    def __str__(self) -> str:
        """Return the N-number, with the make and model in parentheses when known."""
        descriptor = " ".join(p for p in (self.make, self.model) if p)
        return f"{self.n_number} ({descriptor})" if descriptor else self.n_number

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the record after normalizing ``n_number`` to canonical form."""
        self.n_number = normalize_n_number(self.n_number)
        super().save(*args, **kwargs)

    @property
    def insurance_is_current(self) -> bool:
        """Return whether an insurance expiration date is on file and not yet past."""
        if self.insurance_expiration is None:
            return False
        return self.insurance_expiration >= timezone.localdate()

    @property
    def insurance_summary(self) -> str:
        """e.g. ``$1,000,000 / $100,000 \u00b7 exp 2027-03-01``."""
        if not self.insurance_liability_per_occurrence_cents and not self.insurance_expiration:
            return "No insurance on file"
        parts: list[str] = []
        if self.insurance_liability_per_occurrence_cents:
            occurrence = self.insurance_liability_per_occurrence_cents // 100
            person = self.insurance_liability_per_person_cents // 100
            parts.append(f"${occurrence:,} / ${person:,}")
        if self.insurance_expiration:
            parts.append(f"exp {self.insurance_expiration.isoformat()}")
        return " \u00b7 ".join(parts)

    @property
    def display_name(self) -> str:
        """Return the N-number, with the make and model after an em dash when known."""
        descriptor = " ".join(p for p in (self.make, self.model) if p)
        return f"{self.n_number} \u2014 {descriptor}" if descriptor else self.n_number


class AircraftChangeKind(models.TextChoices):
    """Whether a change put a register record there or altered it."""

    CREATED = "created", "Created"
    UPDATED = "updated", "Updated"


class AircraftChange(models.Model):
    """One write to a register record: who made it, when, and what moved.

    A register record is shared by every member who flies the airframe, so an
    edit to its insurance is an edit to everybody's answer.  The history says
    who last touched it and which columns they touched, which is what lets an
    administrator tell a correction from a renewal.  ``fields`` is empty for a
    ``created`` row: the whole record is the change.
    """

    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, related_name="changes")
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aircraft_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=8, choices=AircraftChangeKind.choices)
    fields = models.JSONField(default=list, blank=True)

    class Meta:
        # The primary key breaks the tie between two changes written in the same
        # instant, so a history never comes back in an undefined order.
        ordering = ["-changed_at", "-id"]
        indexes = [models.Index(fields=["aircraft", "-changed_at"], name="aircraft_change_idx")]

    def __str__(self) -> str:
        """Return the registration and the kind, e.g. ``N172SP updated``."""
        return f"{self.aircraft.n_number} {self.kind}"
