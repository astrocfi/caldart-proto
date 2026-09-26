"""Members domain: MemberProfile, MembershipPlan, Membership.

The teams themselves live in ``apps.darts``: a DART outlives any one
membership, and it carries its own airports and its own people.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone

from caldart.models import TimestampedModel
from caldart.phone import normalize_phone


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


#: Values allowed in ``MemberProfile.ratings``, in the two rows the forms show:
#: the category and class ratings, then the instructor ones.
RATING_CHOICES: tuple[tuple[str, str], ...] = (
    ("asel", "ASEL"),
    ("amel", "AMEL"),
    ("ases", "ASES"),
    ("ames", "AMES"),
    ("helicopter", "Helicopter"),
    ("instrument", "Instrument"),
    ("cfi", "CFI"),
    ("cfii", "CFII"),
    ("mei", "MEI"),
)
RATING_VALUES: tuple[str, ...] = tuple(value for value, _ in RATING_CHOICES)

#: The two-letter codes a US address may carry: the fifty states, the District
#: of Columbia, and the territories with USPS codes.
US_STATE_CHOICES: tuple[tuple[str, str], ...] = (
    ("AL", "Alabama"),
    ("AK", "Alaska"),
    ("AZ", "Arizona"),
    ("AR", "Arkansas"),
    ("CA", "California"),
    ("CO", "Colorado"),
    ("CT", "Connecticut"),
    ("DE", "Delaware"),
    ("DC", "District of Columbia"),
    ("FL", "Florida"),
    ("GA", "Georgia"),
    ("HI", "Hawaii"),
    ("ID", "Idaho"),
    ("IL", "Illinois"),
    ("IN", "Indiana"),
    ("IA", "Iowa"),
    ("KS", "Kansas"),
    ("KY", "Kentucky"),
    ("LA", "Louisiana"),
    ("ME", "Maine"),
    ("MD", "Maryland"),
    ("MA", "Massachusetts"),
    ("MI", "Michigan"),
    ("MN", "Minnesota"),
    ("MS", "Mississippi"),
    ("MO", "Missouri"),
    ("MT", "Montana"),
    ("NE", "Nebraska"),
    ("NV", "Nevada"),
    ("NH", "New Hampshire"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),  # codespell:ignore nd
    ("OH", "Ohio"),
    ("OK", "Oklahoma"),
    ("OR", "Oregon"),
    ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"),
    ("SC", "South Carolina"),
    ("SD", "South Dakota"),
    ("TN", "Tennessee"),
    ("TX", "Texas"),
    ("UT", "Utah"),
    ("VT", "Vermont"),
    ("VA", "Virginia"),
    ("WA", "Washington"),
    ("WV", "West Virginia"),
    ("WI", "Wisconsin"),
    ("WY", "Wyoming"),
    ("AS", "American Samoa"),
    ("GU", "Guam"),
    ("MP", "Northern Mariana Islands"),
    ("PR", "Puerto Rico"),
    ("VI", "US Virgin Islands"),
)
US_STATE_VALUES: tuple[str, ...] = tuple(code for code, _ in US_STATE_CHOICES)

#: California's fifty-eight counties.  A member outside California leaves the
#: county blank; the field names the county a DART would call on.
CALIFORNIA_COUNTIES: tuple[str, ...] = (
    "Alameda",
    "Alpine",
    "Amador",
    "Butte",
    "Calaveras",
    "Colusa",
    "Contra Costa",
    "Del Norte",
    "El Dorado",
    "Fresno",
    "Glenn",
    "Humboldt",
    "Imperial",
    "Inyo",
    "Kern",
    "Kings",
    "Lake",
    "Lassen",
    "Los Angeles",
    "Madera",
    "Marin",
    "Mariposa",
    "Mendocino",
    "Merced",
    "Modoc",
    "Mono",
    "Monterey",
    "Napa",
    "Nevada",
    "Orange",
    "Placer",
    "Plumas",
    "Riverside",
    "Sacramento",
    "San Benito",
    "San Bernardino",
    "San Diego",
    "San Francisco",
    "San Joaquin",
    "San Luis Obispo",
    "San Mateo",
    "Santa Barbara",
    "Santa Clara",
    "Santa Cruz",
    "Shasta",
    "Sierra",
    "Siskiyou",
    "Solano",
    "Sonoma",
    "Stanislaus",
    "Sutter",
    "Tehama",
    "Trinity",
    "Tulare",
    "Tuolumne",
    "Ventura",
    "Yolo",
    "Yuba",
)

#: The most hours a logbook entry may claim.  A larger number is a typo: the
#: highest civil totals on record are under 60,000.
MAX_TOTAL_HOURS = 99_999


class MemberProfile(TimestampedModel):
    """Everything the join form collects, plus admin-only notes."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    # -- contact ----------------------------------------------------------
    #: Every number is stored as ``XXX-XXX-XXXX``: one shape to read, to search
    #: on and to print, rather than a dozen spellings to clean up afterwards.
    phone = models.CharField(max_length=12, blank=True)
    phone_extension = models.CharField(max_length=6, blank=True)
    phone_alt = models.CharField(max_length=12, blank=True)
    phone_alt_extension = models.CharField(max_length=6, blank=True)
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True, choices=US_STATE_CHOICES, default="CA")
    postal_code = models.CharField(max_length=5, blank=True)
    county = models.CharField(
        "California county",
        max_length=120,
        blank=True,
        choices=[(name, name) for name in CALIFORNIA_COUNTIES],
    )
    emergency_contact_name = models.CharField(max_length=160, blank=True)
    emergency_contact_phone = models.CharField(max_length=12, blank=True)
    emergency_contact_phone_extension = models.CharField(max_length=6, blank=True)

    # -- aviation ---------------------------------------------------------
    home_airport_identifier = models.CharField(max_length=3, blank=True)
    home_airport_city = models.CharField(max_length=120, blank=True)
    dart = models.ForeignKey(
        "darts.Dart", on_delete=models.SET_NULL, null=True, blank=True, related_name="members"
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
    #: A member who rents or borrows has no airframe to list, and a DART leader
    #: needs to know that is the reason rather than an empty profile.
    flies_rented_aircraft = models.BooleanField("flies rented or borrowed aircraft", default=False)

    # -- volunteer interests ---------------------------------------------
    vol_mission_pilot = models.BooleanField("mission pilot", default=False)
    vol_ground_team = models.BooleanField("ground support", default=False)
    vol_exercise_training = models.BooleanField("exercises and training", default=False)
    vol_member_support = models.BooleanField("member support", default=False)
    vol_fundraising = models.BooleanField("fundraising", default=False)
    vol_social_media = models.BooleanField("social media", default=False)
    vol_newsletter = models.BooleanField("newsletter", default=False)

    # -- membership -------------------------------------------------------
    #: The day this person first joined, set when their first term is created
    #: and never moved by a renewal or by a gap in their membership.
    member_since = models.DateField(null=True, blank=True)

    #: When profile information was last written: a member's own edit, an
    #: administrator's edit to the profile or to the account's name or email,
    #: an aircraft attached or detached, or the profile's creation.  ``NULL``
    #: until one of those happens, so a seeded profile nobody has touched
    #: answers ``NULL``.  Set only by ``apps.members.services.touch_profile``;
    #: never by a payment, a membership grant or renewal, a reminder, or a
    #: role change.
    profile_updated_at = models.DateTimeField(null=True, blank=True)

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
        "state",
        "postal_code",
        "pilot_certificate_type",
    )

    #: The fields ``save`` puts into canonical phone form.
    PHONE_FIELDS = ("phone", "phone_alt", "emergency_contact_phone")

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the profile with every phone number in ``XXX-XXX-XXXX`` form.

        A number that cannot be read as ten digits is stored as it was typed, so
        nothing is invented here; the serializer refuses it at the boundary.
        """
        for field in self.PHONE_FIELDS:
            setattr(self, field, normalize_phone(getattr(self, field)))
        super().save(*args, **kwargs)

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
        return f"{self.name} ({self.price_display})"

    @property
    def price_display(self) -> str:
        """The price in dollars with a leading dollar sign, e.g. ``$45.00``."""
        return f"${self.price_cents / 100:,.2f}"

    @property
    def is_lifetime(self) -> bool:
        """True when the plan never runs out, which is what a blank duration means."""
        return self.duration_days is None


class MembershipStatusChoices(models.TextChoices):
    """The stored state of one ``Membership`` term.

    ``SUSPENDED`` is a term whose holder deactivated their own account while it still
    had time to run.  It counts for nothing -- it never covers a day and never makes
    anybody expired -- until the account is reactivated, when it becomes ``ACTIVE``
    again, or ``EXPIRED`` if it ran out in the meantime.  It still makes its holder a
    member for ``members.services.account_kind`` once it has started, so a deactivated
    member's kind stays ``member`` while their membership state reads ``friend``.
    """

    ACTIVE = "active", "Active"
    EXPIRED = "expired", "Expired"
    CANCELED = "canceled", "Canceled"
    SUSPENDED = "suspended", "Suspended"


class MembershipState(models.TextChoices):
    """The computed answer to "is this person a current member".

    Unlike ``MembershipStatusChoices`` this is never stored: it is what
    ``members.services.membership_status`` works out from every term an account
    holds and from the account's effective kind (``members.services.account_kind``).
    ``CURRENT`` is a term covering today and ``EXPIRED`` a term that has started and
    run out.  ``FRIEND`` is a friend of CalDART, who pays no dues and so is never
    current and never expired, whatever terms they held as a member; that includes
    anybody who chose to be a member and has not yet paid.  ``DONOR`` is what a
    donor account reads, and a donor never appears in a member list.  These labels
    are what the member list's status filter, the member report, and the portal's
    status select all show, so a change here is a change everywhere at once.
    """

    CURRENT = "current", "Current"
    EXPIRED = "expired", "Expired"
    FRIEND = "friend", "Friend"
    DONOR = "donor", "Donor"


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
