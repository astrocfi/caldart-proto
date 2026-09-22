"""Members domain: Dart, MemberProfile, MembershipPlan, Membership."""

from __future__ import annotations

from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone

from caldart.models import TimestampedModel


# ``cms.DartPage`` points here with ``related_name="pages"``, but it is a Wagtail
# page: its base classes are untyped, so django-stubs cannot build the reverse
# manager for the relation and reports it against this end of it.
class Dart(TimestampedModel):  # type: ignore[django-manager-missing]
    """A local Disaster Airlift Response Team."""

    name = models.CharField(max_length=120, unique=True)
    airport_identifier = models.CharField(
        max_length=8, blank=True, help_text="FAA identifier, e.g. E16"
    )
    city = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "DART"
        verbose_name_plural = "DARTs"
        indexes = [models.Index(fields=["is_active", "sort_order"], name="members_dart_active_idx")]

    def __str__(self) -> str:
        """The name, with the airport identifier in parentheses when there is one."""
        if self.airport_identifier:
            return f"{self.name} ({self.airport_identifier})"
        return self.name


class PilotCertificateType(models.TextChoices):
    """The pilot certificate a member holds, or ``NONE`` for a non-pilot."""

    NONE = "none", "None"
    STUDENT = "student", "Student"
    SPORT = "sport", "Sport"
    RECREATIONAL = "recreational", "Recreational"
    PRIVATE = "private", "Private"
    COMMERCIAL = "commercial", "Commercial"
    ATP = "atp", "Airline Transport Pilot"


class IfrRated(models.TextChoices):
    """Whether a pilot holds an instrument rating; ``NA`` for a non-pilot."""

    NA = "na", "Not applicable"
    YES = "yes", "Yes"
    NO = "no", "No"


class MedicalType(models.TextChoices):
    """The medical certificate a member holds, or ``NONE`` for none on file."""

    NONE = "none", "None"
    BASICMED = "basicmed", "BasicMed"
    FIRST = "first", "First class"
    SECOND = "second", "Second class"
    THIRD = "third", "Third class"


#: Values allowed in ``MemberProfile.ratings``.
RATING_CHOICES: tuple[tuple[str, str], ...] = (
    ("instrument", "Instrument"),
    ("multi_engine", "Multi-engine"),
    ("cfi", "CFI"),
    ("cfii", "CFII"),
    ("mei", "MEI"),
    ("seaplane", "Seaplane"),
    ("helicopter", "Helicopter"),
    ("glider", "Glider"),
)
RATING_VALUES: tuple[str, ...] = tuple(value for value, _ in RATING_CHOICES)


class MemberProfile(TimestampedModel):
    """Everything the join form collects, plus admin-only notes."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    # -- contact ----------------------------------------------------------
    phone = models.CharField(max_length=32, blank=True)
    phone_alt = models.CharField(max_length=32, blank=True)
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True, default="CA")
    postal_code = models.CharField(max_length=12, blank=True)
    county = models.CharField(max_length=120, blank=True)
    emergency_contact_name = models.CharField(max_length=160, blank=True)
    emergency_contact_phone = models.CharField(max_length=32, blank=True)

    # -- aviation ---------------------------------------------------------
    home_airport_identifier = models.CharField(max_length=8, blank=True)
    home_airport_city = models.CharField(max_length=120, blank=True)
    dart = models.ForeignKey(
        Dart, on_delete=models.SET_NULL, null=True, blank=True, related_name="members"
    )
    air_care_alliance_number = models.CharField(max_length=40, blank=True)
    pilot_certificate_type = models.CharField(
        max_length=16, choices=PilotCertificateType.choices, default=PilotCertificateType.NONE
    )
    certificate_number = models.CharField(max_length=40, blank=True)
    ifr_rated = models.CharField(max_length=4, choices=IfrRated.choices, default=IfrRated.NA)
    ratings = models.JSONField(default=list, blank=True)
    medical_type = models.CharField(
        max_length=16, choices=MedicalType.choices, default=MedicalType.NONE
    )
    medical_expiration = models.DateField(null=True, blank=True)
    flight_review_date = models.DateField(null=True, blank=True)
    total_hours = models.PositiveIntegerField(null=True, blank=True)
    aircraft = models.ManyToManyField(
        "aircraft.Aircraft", blank=True, related_name="pilots", verbose_name="planes commonly flown"
    )

    # -- volunteer interests ---------------------------------------------
    vol_ground_team = models.BooleanField("ground team", default=False)
    vol_exercise_training = models.BooleanField("exercises and training", default=False)
    vol_member_support = models.BooleanField("member support", default=False)
    vol_fundraising = models.BooleanField("fundraising", default=False)
    vol_social_media = models.BooleanField("social media", default=False)
    vol_newsletter = models.BooleanField("newsletter", default=False)

    # -- admin only -------------------------------------------------------
    notes = models.TextField(blank=True)
    how_heard = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name"]
        verbose_name = "member profile"
        verbose_name_plural = "member profiles"
        indexes = [
            models.Index(fields=["medical_expiration"], name="members_prof_medexp_idx"),
            models.Index(fields=["pilot_certificate_type"], name="members_prof_cert_idx"),
        ]

    def __str__(self) -> str:
        """``Profile for`` the member's display name."""
        return f"Profile for {self.display_name}"

    @property
    def display_name(self) -> str:
        """The member's full name, falling back to their email address.

        The name is both parts joined by a space, trimmed, so a record holding
        only a first name reads as that name alone.
        """
        full = f"{self.user.first_name} {self.user.last_name}".strip()
        return full or self.user.email

    @property
    def medical_is_current(self) -> bool:
        """BasicMed and class medicals both use the stored expiration date."""
        if self.medical_type == MedicalType.NONE or self.medical_expiration is None:
            return False
        return self.medical_expiration >= timezone.localdate()

    #: The fields ``profile_complete`` requires.  One list, used by
    #: :py:meth:`is_complete`, by the ``user`` payload the API returns, and --
    #: mirrored -- by the portal's profile form, so the join wizard can never
    #: accept a profile the server then calls incomplete.
    COMPLETE_FIELDS = (
        "phone",
        "address_line1",
        "city",
        "postal_code",
        "pilot_certificate_type",
    )

    @property
    def is_complete(self) -> bool:
        """Enough detail entered for the portal to stop nagging.

        ``pilot_certificate_type`` is tested for *a value*, not for "not
        ``none``": a ground-team volunteer who has genuinely answered "Not a
        pilot" has finished the form.
        """
        return all(getattr(self, field, "") for field in self.COMPLETE_FIELDS)


class MembershipPlan(TimestampedModel):
    """A purchasable membership term."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    price_cents = models.PositiveIntegerField()
    duration_days = models.PositiveIntegerField(
        null=True, blank=True, help_text="Blank means a lifetime membership."
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "membership plan"
        verbose_name_plural = "membership plans"

    def __str__(self) -> str:
        """The plan name and its price in dollars, e.g. ``Annual ($45.00)``."""
        return f"{self.name} (${self.price_cents / 100:,.2f})"

    @property
    def is_lifetime(self) -> bool:
        """True when the plan never runs out, which is what a blank duration means."""
        return self.duration_days is None


class MembershipStatusChoices(models.TextChoices):
    """The stored state of one ``Membership`` term."""

    ACTIVE = "active", "Active"
    EXPIRED = "expired", "Expired"
    CANCELED = "canceled", "Canceled"


class MembershipState(models.TextChoices):
    """The computed answer to "is this person a current member".

    Unlike ``MembershipStatusChoices`` this is never stored: it is what
    ``members.services.membership_status`` works out from every term an account
    holds, and the three values partition the member table.  ``NONE`` means
    nothing has started, not that a term was canceled.
    """

    CURRENT = "current", "Current"
    EXPIRED = "expired", "Expired"
    NONE = "none", "Never a member"


class MembershipSource(models.TextChoices):
    """How a term was come by: paid for, granted by hand, or seeded."""

    PAYMENT = "payment", "Payment"
    MANUAL = "manual", "Manual grant"
    SEED = "seed", "Seed data"


class Membership(TimestampedModel):
    """One paid or granted membership term."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name="memberships")
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True, help_text="Blank means lifetime.")
    status = models.CharField(
        max_length=12,
        choices=MembershipStatusChoices.choices,
        default=MembershipStatusChoices.ACTIVE,
    )
    source = models.CharField(
        max_length=12, choices=MembershipSource.choices, default=MembershipSource.PAYMENT
    )
    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="membership",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memberships_granted",
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-starts_on", "-id"]
        indexes = [
            models.Index(fields=["user", "-ends_on"], name="members_mship_user_end_idx"),
            models.Index(fields=["status", "ends_on"], name="members_mship_status_idx"),
        ]

    def __str__(self) -> str:
        """The member, the plan name and the dates, with ``lifetime`` for no end."""
        end = self.ends_on.isoformat() if self.ends_on else "lifetime"
        return f"{self.user} \u00b7 {self.plan.name} \u00b7 {self.starts_on.isoformat()}-{end}"

    @property
    def is_lifetime(self) -> bool:
        """True when the term never runs out, which is what a blank ``ends_on`` means."""
        return self.ends_on is None

    def covers(self, on_date: date | None = None) -> bool:
        """True when this term is active and covers ``on_date`` (default today)."""
        if self.status != MembershipStatusChoices.ACTIVE:
            return False
        on_date = on_date or timezone.localdate()
        if self.starts_on > on_date:
            return False
        return self.ends_on is None or self.ends_on >= on_date
