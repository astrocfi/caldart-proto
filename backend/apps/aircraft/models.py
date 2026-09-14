"""Aircraft register with insurance data."""

from __future__ import annotations

import re

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.members.models import TimestampedModel

_N_NUMBER_STRIP = re.compile(r"[^A-Za-z0-9]")


def normalize_n_number(value: str | None) -> str:
    """Normalise a US registration to canonical ``N#####`` form.

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
        descriptor = " ".join(p for p in (self.make, self.model) if p)
        return f"{self.n_number} ({descriptor})" if descriptor else self.n_number

    def save(self, *args, **kwargs):
        self.n_number = normalize_n_number(self.n_number)
        return super().save(*args, **kwargs)

    @property
    def insurance_is_current(self) -> bool:
        if self.insurance_expiration is None:
            return False
        return self.insurance_expiration >= timezone.localdate()

    @property
    def insurance_summary(self) -> str:
        """e.g. ``$1,000,000 / $100,000 · exp 2027-03-01``."""
        if not self.insurance_liability_per_occurrence_cents and not self.insurance_expiration:
            return "No insurance on file"
        parts: list[str] = []
        if self.insurance_liability_per_occurrence_cents:
            occurrence = self.insurance_liability_per_occurrence_cents // 100
            person = self.insurance_liability_per_person_cents // 100
            parts.append(f"${occurrence:,} / ${person:,}")
        if self.insurance_expiration:
            parts.append(f"exp {self.insurance_expiration.isoformat()}")
        return " · ".join(parts)

    @property
    def display_name(self) -> str:
        descriptor = " ".join(p for p in (self.make, self.model) if p)
        return f"{self.n_number} — {descriptor}" if descriptor else self.n_number
