"""factory_boy factories for every CalDART model."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, TypeVar, cast

import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Model
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.accounts.roles import MEMBER
from apps.aircraft.models import Aircraft, OwnerType
from apps.members.models import (
    Dart,
    IfrRated,
    MedicalType,
    MemberProfile,
    Membership,
    MembershipPlan,
    MembershipSource,
    MembershipStatusChoices,
    PilotCertificateType,
)
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, PaymentWallet
from apps.reminders.models import ReminderKind, ReminderLog

if TYPE_CHECKING:
    from apps.accounts.models import User as UserModel
    from apps.cms.models import HomePage, SiteSettings

User = get_user_model()

DEFAULT_PASSWORD = "test-password-123"  # noqa: S105 - test fixture

ModelT = TypeVar("ModelT", bound=Model)


class ModelFactory(DjangoModelFactory[ModelT]):
    """Base for the factories below, declaring the model type that calling one returns.

    Every factory here is a ``ModelFactory[SomeModel]``, and calling it saves and
    returns a ``SomeModel``. Subclasses give their model in ``Meta.model`` as usual.
    """

    class Meta:
        abstract = True

    # factory_boy builds through an unannotated metaclass ``__call__``, which a type
    # checker cannot read, so it would infer the factory class itself.  Declaring
    # ``__new__`` states the real result type; the metaclass never reaches this body.
    def __new__(cls, **kwargs: Any) -> ModelT:  # type: ignore[misc]
        """Return the saved model instance that calling the factory builds."""
        raise NotImplementedError


class GroupFactory(ModelFactory[Group]):
    """Builds an auth ``Group``, reusing an existing row with the same name."""

    class Meta:
        model = Group
        django_get_or_create = ["name"]

    name = MEMBER


class UserFactory(ModelFactory["UserModel"]):
    """Builds a ``User``, reusing an existing row with the same email.

    ``roles=[...]`` grants each named role slug through ``User.add_role`` after
    creation; omitting it leaves the user with no roles. The user's password is set to
    ``DEFAULT_PASSWORD`` unless ``password=...`` supplies another plaintext value.
    """

    class Meta:
        model = User
        django_get_or_create = ["email"]
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.test")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True

    # factory.post_generation is untyped (a factory_boy stub gap), which otherwise
    # makes the decorated function untyped too under strict mode.
    @factory.post_generation  # type: ignore[untyped-decorator]
    def password(self: UserModel, create: bool, extracted: str | None, **kwargs: Any) -> None:
        """Set the password to ``extracted``, falling back to ``DEFAULT_PASSWORD``."""
        if not create:
            return
        self.set_password(extracted or DEFAULT_PASSWORD)
        self.save(update_fields=["password"])

    @factory.post_generation  # type: ignore[untyped-decorator]
    def roles(self: UserModel, create: bool, extracted: list[str] | None, **kwargs: Any) -> None:
        """Grant the user each role slug in ``extracted``, or none if it is falsy."""
        if not create or not extracted:
            return
        for slug in extracted:
            self.add_role(slug)


class DartFactory(ModelFactory[Dart]):
    """Builds a ``Dart``, reusing an existing row with the same name."""

    class Meta:
        model = Dart
        django_get_or_create = ["name"]

    name = factory.Sequence(lambda n: f"Test DART {n}")
    airport_identifier = factory.Sequence(lambda n: f"T{n:02d}")
    city = factory.Faker("city")
    is_active = True
    sort_order = factory.Sequence(lambda n: n)


class AircraftFactory(ModelFactory[Aircraft]):
    """Builds an ``Aircraft``, reusing an existing row with the same N-number."""

    class Meta:
        model = Aircraft
        django_get_or_create = ["n_number"]

    n_number = factory.Sequence(lambda n: f"N{5000 + n}X")
    make = "Cessna"
    model = "182T Skylane"
    year = 2008
    owner_type = OwnerType.INDIVIDUAL
    owner_name = factory.Faker("name")
    owner_contact = factory.Faker("email")
    seats = 4
    insurance_carrier = "Avemco"
    insurance_policy_number = factory.Sequence(lambda n: f"AV-{n:08d}")
    insurance_liability_per_occurrence_cents = 100_000_000
    insurance_liability_per_person_cents = 10_000_000
    insurance_hull_cents = 20_000_000
    insurance_expiration = factory.LazyFunction(lambda: timezone.localdate() + timedelta(days=200))
    is_active = True


class MemberProfileFactory(ModelFactory[MemberProfile]):
    """Builds a ``MemberProfile``, reusing an existing row for the same user."""

    class Meta:
        model = MemberProfile
        django_get_or_create = ["user"]

    user = factory.SubFactory(UserFactory)
    phone = factory.Faker("numerify", text="###-###-####")
    address_line1 = factory.Faker("street_address")
    city = factory.Faker("city")
    state = "CA"
    postal_code = factory.Faker("numerify", text="9####")
    county = "Santa Clara"
    dart = factory.SubFactory(DartFactory)
    pilot_certificate_type = PilotCertificateType.PRIVATE
    certificate_number = factory.Faker("numerify", text="#######")
    ifr_rated = IfrRated.YES
    ratings = factory.LazyFunction(lambda: ["instrument"])
    medical_type = MedicalType.THIRD
    medical_expiration = factory.LazyFunction(lambda: timezone.localdate() + timedelta(days=365))
    total_hours = 750


class MembershipPlanFactory(ModelFactory[MembershipPlan]):
    """Builds an annual ``MembershipPlan``, reusing an existing row with the same slug."""

    class Meta:
        model = MembershipPlan
        django_get_or_create = ["slug"]

    name = "Annual"
    slug = "annual"
    price_cents = 4_500
    duration_days: int | None = 365
    is_active = True
    sort_order = 1


class LifetimePlanFactory(MembershipPlanFactory):
    """Builds a lifetime ``MembershipPlan`` (``duration_days`` is ``None``)."""

    name = "Life"
    slug = "life"
    price_cents = 65_000
    duration_days = None
    sort_order = 2


class PaymentFactory(ModelFactory[Payment]):
    """Builds a pending mock ``Payment`` of 4,500 cents, whatever plan it names."""

    class Meta:
        model = Payment

    user = factory.SubFactory(UserFactory)
    plan = factory.SubFactory(MembershipPlanFactory)
    amount_cents = 4_500
    plan_amount_cents = 4_500
    contribution_cents = 0
    currency = "usd"
    provider = PaymentProvider.MOCK
    wallet = PaymentWallet.MOCK
    provider_ref = factory.Sequence(lambda n: f"test_ref_{n}")
    status = PaymentStatus.PENDING


class MembershipFactory(ModelFactory[Membership]):
    """Builds an active ``Membership`` starting today, ending per the plan's duration."""

    class Meta:
        model = Membership

    user = factory.SubFactory(UserFactory)
    plan = factory.SubFactory(MembershipPlanFactory)
    starts_on = factory.LazyFunction(timezone.localdate)
    ends_on = factory.LazyAttribute(
        lambda o: (
            None
            if o.plan.duration_days is None
            else o.starts_on + timedelta(days=o.plan.duration_days - 1)
        )
    )
    status = MembershipStatusChoices.ACTIVE
    source = MembershipSource.SEED


class ReminderLogFactory(ModelFactory[ReminderLog]):
    """Builds a T-30 ``ReminderLog`` sent now, addressed to its own ``user``.

    ``user`` and ``membership`` default to independent new records, so ``to_email`` is
    the log user's email and not the membership owner's. Pass both to record a reminder
    about a member's own membership.
    """

    class Meta:
        model = ReminderLog

    user = factory.SubFactory(UserFactory)
    membership = factory.SubFactory(MembershipFactory)
    kind = ReminderKind.T30
    sent_at = factory.LazyFunction(timezone.now)
    to_email = factory.LazyAttribute(lambda o: o.user.email)


def make_home_page(title: str = "Home") -> HomePage:
    """Return the site's Wagtail ``HomePage``, creating it under the tree root if needed.

    If a ``HomePage`` already exists, returns it unchanged and ignores ``title``.
    """
    from wagtail.models import Page

    from apps.cms.models import HomePage

    existing = HomePage.objects.first()
    if existing is not None:
        # Wagtail's Page base class is untyped, so its queryset methods return Any.
        return cast("HomePage", existing)
    root = Page.get_first_root_node()
    home = HomePage(title=title, slug="home")
    root.add_child(instance=home)
    home.save_revision().publish()
    return home


def make_site_settings(**kwargs: Any) -> SiteSettings:
    """Return the default site's ``SiteSettings`` row, creating it if needed.

    Creates the default ``Site`` (rooted at ``make_home_page()``) when none exists, then
    creates or updates its ``SiteSettings`` row with the field values in ``kwargs``.
    """
    from wagtail.models import Site

    from apps.cms.models import SiteSettings

    site = Site.objects.filter(is_default_site=True).first()
    if site is None:
        site = Site.objects.create(
            hostname="localhost",
            port=80,
            site_name="CalDART",
            root_page=make_home_page(),
            is_default_site=True,
        )
    obj, _ = SiteSettings.objects.update_or_create(site=site, defaults=kwargs)
    # Wagtail's Site model is untyped, so update_or_create's return is Any.
    return cast("SiteSettings", obj)
