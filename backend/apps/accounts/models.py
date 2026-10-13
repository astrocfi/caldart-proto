"""Accounts: the custom ``User`` (email login) and its role helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from django.contrib.auth.models import AbstractUser, Group
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.accounts.roles import ROLE_SLUGS, STAFF_ROLE_SLUGS, SYSTEM_ADMIN
from caldart.casing import person_last_name, person_name
from caldart.models import TimestampedModel

if TYPE_CHECKING:
    # Inline: members sits above accounts in the app order, so even a type-only
    # import of it may not be top-level.
    from apps.members.services import MembershipStatusDict


class AccountKind(models.TextChoices):
    """What kind of person an account belongs to.

    A ``MEMBER`` pays dues and is expected to keep paying; a ``FRIEND`` has a portal
    account and no dues, so is never current and never expired; a ``DONOR`` gave
    through the public site, holds no password and no role, and cannot sign in.
    """

    MEMBER = "member", "Member"
    FRIEND = "friend", "Friend"
    DONOR = "donor", "Donor"


#: The kinds a person may choose at registration and an administrator may set by
#: hand.  Nobody is made a donor by hand, and a donor changes kind only by
#: registering.
PERSON_KINDS: tuple[AccountKind, ...] = (AccountKind.MEMBER, AccountKind.FRIEND)

#: ``PERSON_KINDS`` as a choice list, for the serializers that accept one.
PERSON_KIND_CHOICES: list[tuple[str, str]] = [(kind.value, kind.label) for kind in PERSON_KINDS]


class UserManager(DjangoUserManager["User"]):
    """Manager for a user model whose natural key is ``email``."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> User:
        """Create, save, and return a user with ``email`` and ``password``.

        The address is normalized and stripped before it is stored.  ``extra_fields``
        are set on the row as given.  Without a password the account holds an unusable
        one.  Raises ``ValueError`` with "Users must have an email address" when
        ``email`` is empty.
        """
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email).strip()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(  # type: ignore[override]  # django-stubs types the base on `username`
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        """Create an ordinary account: neither staff nor superuser unless asked.

        ``extra_fields`` may override either flag.  Raises ``ValueError`` when ``email``
        is empty.
        """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(  # type: ignore[override]  # django-stubs types the base on `username`
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        """Create an account with both the staff and superuser flags set.

        ``manage.py createsuperuser`` reaches this.  Raises ``ValueError`` when
        ``extra_fields`` turns either flag off, with "Superuser must have
        is_staff=True." or "Superuser must have is_superuser=True.", and when
        ``email`` is empty.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username: str | None) -> User:
        """The user whose email address is ``username``, compared case-insensitively.

        Authentication and ``manage.py`` both reach this.  Raises ``User.DoesNotExist``
        when no account matches, including when ``username`` is ``None``: the column is
        never null, so a null lookup matches nothing.
        """
        return self.get(email__iexact=username)


class User(AbstractUser):
    """Site user.  ``email`` is the login; there is no ``username``."""

    username = None  # type: ignore[assignment]
    email = models.EmailField("email address", unique=True)
    first_name = models.CharField("first name", max_length=150, blank=True)
    last_name = models.CharField("last name", max_length=150, blank=True)

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    #: When the account's owner last proved the address is theirs, by following a
    #: verification or password link sent to it; ``None`` while it is unverified.
    email_verified_at = models.DateTimeField(null=True, blank=True)
    #: When the bounce check last read a permanent-failure report for a message sent to
    #: the current address; ``None`` while no bounce is known.  Cleared, with
    #: ``email_bounce_detail``, when the address changes, when it is verified, and by a
    #: user administrator's **Clear bounce**.
    email_bounced_at = models.DateTimeField(null=True, blank=True)
    #: That report's status code and diagnostic text, or ``""`` with no bounce known.
    email_bounce_detail = models.CharField(max_length=255, blank=True)
    #: The address a requested change of sign-in address moves the account to, or
    #: ``""`` when no change is waiting.  The account keeps signing in with ``email``
    #: until the link mailed to this address is followed; a later request replaces it.
    pending_email = models.EmailField("pending email address", blank=True)
    #: When a link mailed to an earlier address last undid a change of address; every
    #: undo link issued before this moment is spent.  ``None`` until one is followed.
    email_change_undone_at = models.DateTimeField(null=True, blank=True)
    #: The verified address a completed change of address moved the account away from,
    #: kept until ``recovery_until`` so that its owner can undo the change: while it is
    #: kept the address is reserved for this account, the account's own address cannot
    #: change again, and only an undo link mailed to it counts.  ``""`` with none kept.
    recovery_email = models.EmailField("recovery email address", blank=True)
    #: When ``recovery_email`` stops being kept; ``None`` with none kept.
    recovery_until = models.DateTimeField(null=True, blank=True)
    #: The kind of person the account belongs to, as stored: what they asked for.  A
    #: member with a ``friend_on`` date that has arrived, or who has not yet paid,
    #: already counts as a friend: see ``apps.members.services.account_kind``.
    kind = models.CharField(max_length=8, choices=AccountKind.choices, default=AccountKind.MEMBER)
    #: The day a member who asked to become a friend becomes one; ``None`` when no
    #: change is pending.
    friend_on = models.DateField(null=True, blank=True)
    #: Set by a user administrator to keep a deactivated account deactivated: while it
    #: is set, no sign-in, password reset, or registration brings the account back.
    reactivation_blocked = models.BooleanField(default=False)
    #: True for an account an account administrator created on **New member**.  Such a
    #: person has joined already, as a member or a friend, so once the address is
    #: verified their sign-in opens the portal rather than the profile and pay steps.
    admin_created = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["last_name", "first_name", "email"]
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
        ]
        indexes = [
            models.Index(fields=["last_name", "first_name"], name="accounts_user_name_idx"),
        ]

    def __str__(self) -> str:
        """The full name, or the email address when neither name is filled in."""
        return self.get_full_name() or self.email

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Strip the email, normalize both names, and save the row as Django would.

        The first name goes through :func:`caldart.casing.person_name` and the last name
        through :func:`caldart.casing.person_last_name`: trimmed, and title-cased when
        typed entirely in one case.  Doing both here rather than in
        a form means every writer -- registration, the profile, the administrator's
        editor, a donation, the Django admin, a management command -- stores the address
        the unique constraint compares and the same spelling of a name.
        """
        if self.email:
            self.email = self.email.strip()
        self.first_name = person_name(self.first_name)
        self.last_name = person_last_name(self.last_name)
        super().save(*args, **kwargs)

    # -- names ------------------------------------------------------------
    def get_full_name(self) -> str:
        """First and last name joined by a space, stripped; empty when both are blank."""
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        """The first name, or the email address when there is no first name."""
        return self.first_name or self.email

    @property
    def display_name(self) -> str:
        """The full name, or the email address when neither name is filled in."""
        return self.get_full_name() or self.email

    @property
    def email_verified(self) -> bool:
        """True once the owner has proved the current address is theirs."""
        return self.email_verified_at is not None

    # -- roles ------------------------------------------------------------
    @property
    def roles(self) -> list[str]:
        """Role slugs held by this user, in privilege order."""
        held = {g.name for g in self.groups.all()} & set(ROLE_SLUGS)
        return [slug for slug in ROLE_SLUGS if slug in held]

    def has_role(self, slug: str) -> bool:
        """True when the user holds ``slug``.  ``system_admin`` implies all."""
        held = self.roles
        return slug in held or SYSTEM_ADMIN in held

    def has_any_role(self, *slugs: str) -> bool:
        """True when the user holds at least one of ``slugs``.

        A ``system_admin`` passes whatever ``slugs`` names.  Passing no slug at all is
        False for everyone but a system administrator.
        """
        held = set(self.roles)
        if SYSTEM_ADMIN in held:
            return True
        return bool(held & set(slugs))

    def add_role(self, slug: str) -> None:
        """Give the user the role ``slug``, creating its group if it is missing.

        Adding a role the user already holds changes nothing.  The Django staff and
        superuser flags are left alone.
        """
        group, _ = Group.objects.get_or_create(name=slug)
        self.groups.add(group)

    def remove_role(self, slug: str) -> None:
        """Take the role ``slug`` away from the user.

        Removing a role the user does not hold, or one no group exists for, changes
        nothing.  The Django staff and superuser flags are left alone.
        """
        group = Group.objects.filter(name=slug).first()
        if group is not None:
            self.groups.remove(group)

    def set_roles(self, slugs: list[str]) -> None:
        """Replace the user's role groups with exactly ``slugs``."""
        wanted = [s for s in ROLE_SLUGS if s in set(slugs)]
        groups = [Group.objects.get_or_create(name=s)[0] for s in wanted]
        keep = self.groups.exclude(name__in=ROLE_SLUGS)
        self.groups.set(list(keep) + groups)

    # -- membership -------------------------------------------------------
    @property
    def membership_status(self) -> MembershipStatusDict:
        """The membership summary for this account, worked out for today.

        Carries ``status`` (``current``, ``expired``, ``friend``, or ``donor``),
        ``expires_on``, ``plan``, and ``is_lifetime``, and costs a query or two each time
        it is read.
        """
        # Inline: members sits above accounts and apps.members.services imports
        # apps.accounts.services, so a top-level import here would close the cycle.
        from apps.members.services import membership_status

        return membership_status(self)

    @property
    def can_access_members_content(self) -> bool:
        """Current membership, or any role beyond plain ``member``.

        A friend is never current, so a friend without a staff role is refused.
        """
        # Inline: members sits above accounts in the app order, so this module may
        # not depend on it at the top level even though apps.members.models itself
        # imports nothing from accounts.
        from apps.members.models import MembershipState

        if self.is_superuser:
            return True
        if self.membership_status["status"] == MembershipState.CURRENT:
            return True
        return bool(set(self.roles) & set(STAFF_ROLE_SLUGS))


class AccountChangeKind(models.TextChoices):
    """What one entry in an account's history did to it."""

    CREATED = "created", "Created"
    ROLES = "roles", "Roles changed"
    DEACTIVATED = "deactivated", "Deactivated"
    REACTIVATED = "reactivated", "Reactivated"
    BLOCKED = "blocked", "Reactivation blocked"
    UNBLOCKED = "unblocked", "Reactivation allowed"
    NEW_PASSWORD = "new_password", "New password required"
    EMAIL_CHANGED = "email_changed", "Email address changed"
    EMAIL_CHANGE_UNDONE = "email_change_undone", "Email address change undone"
    MFA_RESET = "mfa_reset", "Two-factor reset"


class AccountChange(models.Model):
    """One change to who an account is allowed to be: who made it, when, and what.

    The user record's **History** card reads these back.  An entry is written beside
    the audit line for the same change, for an account an administrator created, a
    role granted or taken away, an account deactivated, reactivated, blocked from
    reactivating, or allowed to reactivate again, a new password required of it, a
    change of sign-in address completed or undone, and two-factor sign-in reset by an
    administrator.  ``changed_by`` is the account that acted, which is the account
    itself when its owner deactivated or reactivated it or undid a change of address,
    the account that asked for a change of address that its new owner completed,
    and ``None`` for a management command (``by_command`` is then true) or an actor
    since deleted.  ``added`` and
    ``removed`` hold role slugs in privilege order, and are empty for every kind but
    ``roles``.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="account_changes")
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="account_changes_made",
    )
    changed_at = models.DateTimeField(default=timezone.now)
    #: True for a change a management command made, which no account stands behind.
    by_command = models.BooleanField(default=False)
    kind = models.CharField(max_length=20, choices=AccountChangeKind.choices)
    added = models.JSONField(default=list, blank=True)
    removed = models.JSONField(default=list, blank=True)

    class Meta:
        # The primary key breaks the tie between two changes written in the same
        # instant, so a history never comes back in an undefined order.
        ordering = ["-changed_at", "-id"]
        indexes = [models.Index(fields=["user", "-changed_at"], name="account_change_idx")]

    def __str__(self) -> str:
        """Return the account id and the kind, e.g. ``account 12 roles``."""
        return f"account {self.user_id} {self.kind}"


class TotpDevice(TimestampedModel):
    """The authenticator app an account signs in with as its second factor.

    One per account.  ``secret`` is the RFC 6238 shared secret in base32, as the
    authenticator app was given it.  ``confirmed_at`` is ``None`` while enrollment is
    under way, and is set once the first code from the app has been accepted: only a
    confirmed device asks for a code at sign-in.  ``last_used_step`` is the 30-second
    time step of the last code accepted, so no code is accepted twice and no code from
    an earlier step is accepted after a later one; ``None`` until a code is accepted.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="totp_device")
    secret = models.CharField(max_length=64)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_used_step = models.BigIntegerField(null=True, blank=True)

    def __str__(self) -> str:
        """Return the account id and whether the device is confirmed."""
        state = "confirmed" if self.confirmed_at is not None else "unconfirmed"
        return f"account {self.user_id} device ({state})"

    @property
    def is_confirmed(self) -> bool:
        """True once a code from the authenticator app has been accepted."""
        return self.confirmed_at is not None


class RecoveryCode(models.Model):
    """One single-use backup code an account may give in place of an authenticator code.

    Only a keyed hash of the code is kept (``apps.accounts.mfa``), with the per-code
    ``salt`` it was computed with.  ``used_at`` is set when the code is spent, after
    which it is never accepted again.  A new set replaces every row of the old one.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recovery_codes")
    salt = models.CharField(max_length=32)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(default=timezone.now)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "used_at"], name="recovery_code_user_idx")]

    def __str__(self) -> str:
        """Return the account id and whether the code is spent."""
        state = "used" if self.used_at is not None else "unused"
        return f"account {self.user_id} recovery code ({state})"


class SignInFailureCount(models.Model):
    """One running count behind the sign-in lockout (``apps.accounts.lockout``).

    ``key`` is a SHA-256 digest naming what is counted -- the fifteen-minute count of
    failed attempts, the day's count of wrong codes, or the day's lockout notice -- and
    whose: an account, or an address no account holds.  ``count`` runs until ``until``,
    after which the row reads as empty and the next failure starts it again.  The rows
    live in the database, so no cache eviction can forget them, and each is updated
    under a row lock.
    """

    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    until = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["until"], name="sign_in_failure_until_idx")]

    def __str__(self) -> str:
        """Return the count and when its window ends."""
        return f"{self.count} until {self.until:%Y-%m-%d %H:%M}"
