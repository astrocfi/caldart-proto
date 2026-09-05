"""Accounts: the custom ``User`` (email login) and its role helpers."""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser, Group
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.accounts.roles import ROLE_SLUGS, STAFF_ROLE_SLUGS, SYSTEM_ADMIN


class UserManager(DjangoUserManager):
    """Manager for a user model whose natural key is ``email``."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email).strip()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username: str):
        return self.get(email__iexact=username)


class User(AbstractUser):
    """Site user.  ``email`` is the login; there is no ``username``."""

    username = None  # type: ignore[assignment]
    email = models.EmailField("email address", unique=True)
    first_name = models.CharField("first name", max_length=150, blank=True)
    last_name = models.CharField("last name", max_length=150, blank=True)

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

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
        return self.get_full_name() or self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip()
        return super().save(*args, **kwargs)

    # -- names ------------------------------------------------------------
    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        return self.first_name or self.email

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.email

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
        held = set(self.roles)
        if SYSTEM_ADMIN in held:
            return True
        return bool(held & set(slugs))

    def add_role(self, slug: str) -> None:
        group, _ = Group.objects.get_or_create(name=slug)
        self.groups.add(group)

    def remove_role(self, slug: str) -> None:
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
    def membership_status(self) -> dict:
        """Delegates to ``members.services.membership_status``."""
        from apps.members.services import membership_status

        return membership_status(self)

    @property
    def can_access_members_content(self) -> bool:
        """Current membership, or any role beyond plain ``member``."""
        if self.is_superuser:
            return True
        if self.membership_status["status"] == "current":
            return True
        return bool(set(self.roles) & set(STAFF_ROLE_SLUGS))
