"""Aircraft register with insurance data."""

from __future__ import annotations

import re
from typing import Any

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.db.models import Value
from django.db.models.functions import Concat
from django.utils import timezone

from caldart.casing import business_name, person_name
from caldart.dates import format_display_date
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


class AircraftCategory(models.TextChoices):
    """What kind of aircraft an airframe is, as the FAA registry classes it."""

    AIRPLANE = "airplane", "Airplane"
    HELICOPTER = "helicopter", "Helicopter"
    GYROPLANE = "gyroplane", "Gyroplane"
    GLIDER = "glider", "Glider"
    BALLOON = "balloon", "Balloon"
    AIRSHIP = "airship", "Airship"
    POWERED_LIFT = "powered_lift", "Powered lift"
    WEIGHT_SHIFT = "weight_shift", "Weight-shift control"
    POWERED_PARACHUTE = "powered_parachute", "Powered parachute"
    OTHER = "other", "Other"


class Airworthiness(models.TextChoices):
    """The classification of an airframe's airworthiness certificate."""

    STANDARD = "standard", "Standard"
    LIMITED = "limited", "Limited"
    RESTRICTED = "restricted", "Restricted"
    EXPERIMENTAL = "experimental", "Experimental"
    PROVISIONAL = "provisional", "Provisional"
    MULTIPLE = "multiple", "Multiple"
    PRIMARY = "primary", "Primary"
    SPECIAL_FLIGHT_PERMIT = "special_flight_permit", "Special flight permit"
    LIGHT_SPORT = "light_sport", "Light sport"


#: The longest value of either choice list, which sizes both columns.
CATEGORY_MAX_LENGTH = 24


class OwnerType(models.TextChoices):
    """Who holds title to an aircraft on the register."""

    INDIVIDUAL = "individual", "Individual"
    FBO = "fbo", "FBO"
    CLUB = "club", "Flying club"


def type_name_expression() -> Concat:
    """The SQL expression ``make || ' ' || model`` over ``AircraftType``.

    The trigram index is built on this expression and the type search compares against
    it, so the two must stay one expression.
    """
    return Concat("make", Value(" "), "model", output_field=models.TextField())


class AircraftType(models.Model):
    """One aircraft type: a manufacturer and model an aircraft is picked from.

    The entries come from the FAA registry's aircraft reference file, one per
    manufacturer-model code (``faa_code``), keeping the FAA's own spellings in
    ``faa_make`` and ``faa_model`` beside the display names every screen prints in
    ``make`` and ``model``.  ``category`` is the FAA's aircraft type for the code
    (blank for a hand-added type).  An entry an account administrator adds by hand, for
    a type the FAA has never registered, has ``is_custom`` set.
    """

    faa_code = models.CharField("FAA code", max_length=16, unique=True)
    faa_make = models.CharField("FAA make", max_length=120)
    faa_model = models.CharField("FAA model", max_length=60)
    make = models.CharField(max_length=120)
    model = models.CharField(max_length=60)
    seats = models.PositiveSmallIntegerField(null=True, blank=True)
    engines = models.PositiveSmallIntegerField(null=True, blank=True)
    category = models.CharField(
        max_length=CATEGORY_MAX_LENGTH, choices=AircraftCategory.choices, blank=True
    )
    is_custom = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["make", "model"]
        verbose_name = "aircraft type"
        indexes = [
            models.Index(fields=["make", "model"], name="aircraft_type_name_idx"),
            GinIndex(
                OpClass(type_name_expression(), name="gin_trgm_ops"),
                name="aircraft_type_trgm_idx",
            ),
        ]

    def __str__(self) -> str:
        """Return the display make and model, e.g. ``Cessna 172S``."""
        return f"{self.make} {self.model}"


class AircraftTypeAlias(models.Model):
    """A lower-case name a person may search by, such as ``c172`` or ``skyhawk``.

    Each alias points at the one aircraft type it names, and deleting the type deletes
    its aliases.
    """

    alias = models.CharField(max_length=40, unique=True)
    type = models.ForeignKey(AircraftType, on_delete=models.CASCADE, related_name="aliases")

    class Meta:
        ordering = ["alias"]
        verbose_name = "aircraft type alias"
        verbose_name_plural = "aircraft type aliases"

    def __str__(self) -> str:
        """Return the alias itself."""
        return self.alias

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the alias stripped and lower-cased, the form a search compares against."""
        self.alias = self.alias.strip().lower()
        super().save(*args, **kwargs)


class RegistrantType(models.TextChoices):
    """Who an FAA registration is held by, as the registry codes it."""

    INDIVIDUAL = "individual", "Individual"
    PARTNERSHIP = "partnership", "Partnership"
    CORPORATION = "corporation", "Corporation"
    CO_OWNED = "co_owned", "Co-owned"
    GOVERNMENT = "government", "Government"
    LLC = "llc", "LLC"
    NON_CITIZEN_CORPORATION = "non_citizen_corporation", "Non-citizen corporation"
    NON_CITIZEN_CO_OWNED = "non_citizen_co_owned", "Non-citizen co-owned"
    UNKNOWN = "unknown", "Unknown"


class RegistrationStatus(models.TextChoices):
    """Whether an FAA registration stands."""

    VALID = "valid", "Valid"
    PENDING = "pending", "Pending"
    REVOKED = "revoked", "Revoked"
    EXPIRED = "expired", "Expired"
    OTHER = "other", "Other"


class Registration(models.Model):
    """One N-number as the FAA registry holds it: the type, the year, and the registrant.

    ``n_number`` is stored normalized as ``Aircraft.n_number`` is, with the leading
    ``N``.  Its uniqueness gives it, on Postgres, a second index built with
    ``varchar_pattern_ops``, which is what serves the N-number typeahead's prefix
    match.  ``airworthiness`` is the classification of the airworthiness certificate,
    blank when the registry gives none.  No address is kept.
    """

    n_number = models.CharField("N-number", max_length=6, unique=True)
    type = models.ForeignKey(AircraftType, on_delete=models.PROTECT, related_name="registrations")
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    registrant_name = models.CharField(max_length=160, blank=True)
    # 24 rather than 16: ``non_citizen_corporation`` is 23 characters.
    registrant_type = models.CharField(
        max_length=24, choices=RegistrantType.choices, default=RegistrantType.UNKNOWN
    )
    status = models.CharField(
        max_length=16, choices=RegistrationStatus.choices, default=RegistrationStatus.VALID
    )
    certificate_issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    airworthiness = models.CharField(
        max_length=CATEGORY_MAX_LENGTH, choices=Airworthiness.choices, blank=True
    )
    imported_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["n_number"]

    def __str__(self) -> str:
        """Return the N-number."""
        return self.n_number

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the record after normalizing ``n_number`` to canonical form."""
        self.n_number = normalize_n_number(self.n_number)
        super().save(*args, **kwargs)


class RegistryImport(models.Model):
    """One run of the FAA registry import, whatever its outcome.

    ``finished_at`` is null while the run is under way; ``ok`` says whether it
    succeeded and ``error`` why it did not.  ``started_by`` is the system administrator
    who started it from the Health and database page, null for a run the timer started.
    """

    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=500, blank=True)
    types_written = models.PositiveIntegerField(default=0)
    registrations_written = models.PositiveIntegerField(default=0)
    types_folded = models.PositiveIntegerField(default=0)
    ok = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registry_imports",
    )

    class Meta:
        ordering = ["-started_at", "-id"]

    def __str__(self) -> str:
        """Return when the run started and whether it succeeded."""
        outcome = "ok" if self.ok else "not ok"
        return f"registry import {self.started_at:%Y-%m-%d %H:%M} ({outcome})"


class Aircraft(TimestampedModel):
    """One airframe, with the insurance a DART leader needs to check.

    ``category`` and ``airworthiness`` are blank until somebody records them; the
    coverage policy (``AircraftCoveragePolicy``) is judged against them.
    """

    n_number = models.CharField("N-number", max_length=12, unique=True)
    type = models.ForeignKey(AircraftType, on_delete=models.PROTECT, related_name="aircraft")
    year = models.PositiveIntegerField(null=True, blank=True)
    owner_type = models.CharField(
        max_length=12, choices=OwnerType.choices, default=OwnerType.INDIVIDUAL
    )
    owner_name = models.CharField(max_length=160, blank=True)
    owner_contact = models.CharField(
        max_length=200, blank=True, help_text="Email or phone, free text."
    )
    seats = models.PositiveSmallIntegerField(null=True, blank=True)
    category = models.CharField(
        max_length=CATEGORY_MAX_LENGTH, choices=AircraftCategory.choices, blank=True
    )
    airworthiness = models.CharField(
        max_length=CATEGORY_MAX_LENGTH, choices=Airworthiness.choices, blank=True
    )

    insurance_carrier = models.CharField(max_length=120, blank=True)
    insurance_policy_number = models.CharField(max_length=60, blank=True)
    insurance_liability_per_occurrence_cents = models.PositiveBigIntegerField(default=0)
    insurance_liability_per_person_cents = models.PositiveBigIntegerField(default=0)
    insurance_hull_cents = models.PositiveBigIntegerField(null=True, blank=True)
    insurance_expiration = models.DateField(null=True, blank=True)
    #: When the insurance was verified and by whom (see ``apps.aircraft.verification``).
    #: Both are ``NULL`` while it is unverified; a write that changes an insurance field
    #: sets them back to ``NULL``.
    insurance_verified_at = models.DateTimeField(null=True, blank=True)
    insurance_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

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
            models.Index(fields=["is_active"], name="aircraft_active_idx"),
        ]

    def __str__(self) -> str:
        """Return the N-number, with the make and model in parentheses when known."""
        descriptor = " ".join(p for p in (self.make, self.model) if p)
        return f"{self.n_number} ({descriptor})" if descriptor else self.n_number

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the record after normalizing ``n_number`` to canonical form.

        An individual owner's name is stored through :func:`caldart.casing.person_name`,
        and any other owner's through :func:`caldart.casing.business_name`, so a name
        the FAA registry filled in capitals reads ``Skyways Aviation LLC`` rather than
        ``SKYWAYS AVIATION LLC``, while a business name typed in mixed case is kept.
        """
        self.n_number = normalize_n_number(self.n_number)
        if self.owner_type == OwnerType.INDIVIDUAL:
            self.owner_name = person_name(self.owner_name)
        else:
            self.owner_name = business_name(self.owner_name)
        super().save(*args, **kwargs)

    @property
    def make(self) -> str:
        """The display make of the aircraft's type, e.g. ``Cessna``."""
        return self.type.make

    @property
    def model(self) -> str:
        """The display model of the aircraft's type, e.g. ``172S``."""
        return self.type.model

    @property
    def insurance_is_current(self) -> bool:
        """Return whether an insurance expiration date is on file and not yet past."""
        if self.insurance_expiration is None:
            return False
        return self.insurance_expiration >= timezone.localdate()

    @property
    def insurance_is_verified(self) -> bool:
        """True when the insurance has been verified.

        Verified insurance whose expiration passes stays verified: currency is
        ``insurance_is_current``, a separate fact.
        """
        return self.insurance_verified_at is not None

    @property
    def insurance_summary(self) -> str:
        """The liability limits and the expiry as a screen shows them.

        For example ``$1,000,000 / $100,000 \u00b7 exp 03/01/2027``, or ``No insurance on
        file`` when neither a limit nor an expiry is recorded.
        """
        if not self.insurance_liability_per_occurrence_cents and not self.insurance_expiration:
            return "No insurance on file"
        parts: list[str] = []
        if self.insurance_liability_per_occurrence_cents:
            occurrence = self.insurance_liability_per_occurrence_cents // 100
            person = self.insurance_liability_per_person_cents // 100
            parts.append(f"${occurrence:,} / ${person:,}")
        if self.insurance_expiration:
            parts.append(f"exp {format_display_date(self.insurance_expiration)}")
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


class AircraftCoveragePolicy(models.Model):
    """The one record of which aircraft CalDART's insurance policy does not cover.

    ``excluded_categories`` holds ``AircraftCategory`` values and
    ``excluded_airworthiness`` ``Airworthiness`` values; an aircraft whose recorded
    category or airworthiness is listed is not covered.  ``note`` is a short plain-text
    statement of the limitation, published to members on My aircraft.  There is only
    ever one row, with primary key 1: :meth:`load` reads it.
    """

    excluded_categories = models.JSONField(default=list, blank=True)
    excluded_airworthiness = models.JSONField(default=list, blank=True)
    note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "aircraft coverage policy"
        verbose_name_plural = "aircraft coverage policy"

    def __str__(self) -> str:
        """Return what the policy excludes, e.g. ``excludes helicopter``."""
        excluded = [*self.excluded_categories, *self.excluded_airworthiness]
        return f"excludes {', '.join(excluded)}" if excluded else "excludes nothing"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the policy as the one row, primary key 1."""
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> AircraftCoveragePolicy:
        """The stored policy, or an unsaved empty one (excluding nothing) before any is.

        Reading never writes: the row first appears when the empty policy is saved.
        """
        return cls.objects.filter(pk=1).first() or cls()
