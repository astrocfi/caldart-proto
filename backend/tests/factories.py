"""factory_boy factories for every CalDART model."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, TypeVar, cast

import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Model
from django.utils import timezone
from factory.django import DjangoModelFactory
from wagtail.models import Page, Site

from apps.accounts.roles import MEMBER
from apps.aircraft.models import Aircraft, OwnerType
from apps.cms.models import (
    ContactPage,
    DartIndexPage,
    DartPage,
    EventIndexPage,
    EventPage,
    HomePage,
    NewsIndexPage,
    NewsPage,
    SiteSettings,
    StandardPage,
)
from apps.darts.models import Dart
from apps.members.models import (
    IfrRated,
    MedicalType,
    MemberProfile,
    Membership,
    MembershipPlan,
    MembershipSource,
    MembershipStatusChoices,
    PilotCertificateType,
)
from apps.payments.models import (
    MandateStatus,
    Payment,
    PaymentProvider,
    PaymentStatus,
    PaymentWallet,
    Refund,
    RefundReason,
    RefundStatus,
    RenewalAttempt,
    RenewalMandate,
)
from apps.reminders.models import ReminderKind, ReminderLog

if TYPE_CHECKING:
    from apps.accounts.models import User as UserModel

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
    airport_identifiers = factory.Sequence(lambda n: f"T{n:02d}")
    city = factory.Faker("city")
    is_active = True


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
    """Builds a pending mock ``Payment`` of 4,500 cents, whatever plan it names.

    ``created_at=<datetime>`` backdates the row after the insert, which is the only
    way to place a payment in a past month: the field is ``auto_now_add``.
    """

    class Meta:
        model = Payment
        skip_postgeneration_save = True

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

    # factory.post_generation is untyped (a factory_boy stub gap), which otherwise
    # makes the decorated function untyped too under strict mode.
    @factory.post_generation  # type: ignore[untyped-decorator]
    def created_at(self: Payment, create: bool, extracted: datetime | None, **kwargs: Any) -> None:
        """Backdate ``created_at`` to ``extracted``, leaving it at now when omitted."""
        if not create or extracted is None:
            return
        Payment.objects.filter(pk=self.pk).update(created_at=extracted)
        self.refresh_from_db(fields=["created_at"])


class RefundFactory(ModelFactory[Refund]):
    """Builds a succeeded 1,000-cent refund against a new succeeded payment.

    The reason is ``requested_by_member`` and no provider reference is set, which is
    what a mock or manual refund looks like.
    """

    class Meta:
        model = Refund

    payment = factory.SubFactory("tests.factories.PaymentFactory", status=PaymentStatus.SUCCEEDED)
    amount_cents = 1_000
    reason = RefundReason.REQUESTED_BY_MEMBER
    status = RefundStatus.SUCCEEDED
    refunded_at = factory.LazyFunction(timezone.now)


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


def make_home_page() -> HomePage:
    """Return the site's Wagtail ``HomePage``, the one the CMS migrations publish.

    The migration that makes a ``HomePage`` the Wagtail site root gives it the slug
    ``home``, so every test database already has exactly one.
    """
    # Wagtail's Page base class is untyped, so its queryset methods return Any.
    return cast("HomePage", HomePage.objects.get(slug="home"))


def make_site_settings(**kwargs: Any) -> SiteSettings:
    """Return the default site's ``SiteSettings`` row, with ``kwargs`` applied to it.

    The CMS migrations create the default ``Site``; this creates or updates the
    ``SiteSettings`` row attached to it with the field values in ``kwargs``.
    """
    site = Site.objects.get(is_default_site=True)
    obj, _ = SiteSettings.objects.update_or_create(site=site, defaults=kwargs)
    # Wagtail's Site model is untyped, so update_or_create's return is Any.
    return cast("SiteSettings", obj)


# -- Wagtail page builders -------------------------------------------------
def publish[P: Page](parent: Page, page: P) -> P:
    """Add ``page`` under ``parent``, publish it, and return it fresh from the database.

    The returned page is re-read through the concrete page class, so its own fields are
    populated rather than only the base ``Page`` ones.
    """
    parent.add_child(instance=page)
    page.save_revision().publish()
    # Wagtail's PageManager is untyped, so `.get()` returns Any; the caller always
    # passes an instance of the page's own concrete class.
    return cast(P, type(page).objects.get(pk=page.pk))


def make_standard_page(
    parent: Page, slug: str = "a-page", title: str = "A page", **fields: Any
) -> StandardPage:
    """Publish a ``StandardPage`` named ``title`` under ``parent`` and return it."""
    return publish(parent, StandardPage(title=title, slug=slug, **fields))


def make_news_index(
    parent: Page, slug: str = "news", title: str = "News", **fields: Any
) -> NewsIndexPage:
    """Publish a ``NewsIndexPage`` named ``title`` under ``parent`` and return it."""
    return publish(parent, NewsIndexPage(title=title, slug=slug, **fields))


def make_news_page(
    parent: Page, slug: str, title: str, *, days_ago: int = 0, **fields: Any
) -> NewsPage:
    """Publish a ``NewsPage`` dated ``days_ago`` days before today and return it."""
    fields.setdefault("date", timezone.localdate() - timedelta(days=days_ago))
    return publish(parent, NewsPage(title=title, slug=slug, **fields))


def make_event_index(
    parent: Page, slug: str = "events", title: str = "Events", **fields: Any
) -> EventIndexPage:
    """Publish an ``EventIndexPage`` named ``title`` under ``parent`` and return it."""
    return publish(parent, EventIndexPage(title=title, slug=slug, **fields))


def make_event_page(
    parent: Page, slug: str, title: str, *, days_ahead: int = 0, **fields: Any
) -> EventPage:
    """Publish an ``EventPage`` dated ``days_ahead`` days from today and return it."""
    fields.setdefault("date", timezone.localdate() + timedelta(days=days_ahead))
    return publish(parent, EventPage(title=title, slug=slug, **fields))


def make_dart_index(
    parent: Page, slug: str = "darts", title: str = "DARTs", **fields: Any
) -> DartIndexPage:
    """Publish a ``DartIndexPage`` named ``title`` under ``parent`` and return it."""
    return publish(parent, DartIndexPage(title=title, slug=slug, **fields))


def make_dart_page(parent: Page, dart: Dart, **fields: Any) -> DartPage:
    """Publish a ``DartPage`` for ``dart`` under ``parent`` and return it.

    The leader's name and contact default to a fictional volunteer unless ``fields``
    supplies them, and the slug is the DART's airport identifier in lower case.
    """
    fields.setdefault("leader_name", "Helen Marchetti")
    fields.setdefault("leader_contact", "helen@example.org")
    slug = dart.airport_identifiers.lower() or "team"
    return publish(parent, DartPage(title=dart.name, slug=slug, dart=dart, **fields))


def make_contact_page(
    parent: Page, slug: str = "contact", title: str = "Contact Us", **fields: Any
) -> ContactPage:
    """Publish a ``ContactPage`` named ``title`` under ``parent`` and return it."""
    return publish(parent, ContactPage(title=title, slug=slug, **fields))


def grant_membership(user: UserModel, plan: MembershipPlan, *, days_left: int = 200) -> Membership:
    """Give ``user`` a term on ``plan`` that stays current for ``days_left`` more days."""
    today = timezone.localdate()
    return MembershipFactory(
        user=user,
        plan=plan,
        starts_on=today - timedelta(days=30),
        ends_on=today + timedelta(days=days_left),
    )


def expire_membership(user: UserModel, plan: MembershipPlan, *, days_ago: int = 30) -> Membership:
    """Give ``user`` a term on ``plan`` that lapsed ``days_ago`` days ago."""
    today = timezone.localdate()
    return MembershipFactory(
        user=user,
        plan=plan,
        starts_on=today - timedelta(days=days_ago + 365),
        ends_on=today - timedelta(days=days_ago),
        status=MembershipStatusChoices.EXPIRED,
    )


class RenewalMandateFactory(ModelFactory[RenewalMandate]):
    """Builds an active mock mandate on a test card ending 4242, no contribution.

    Pass ``plan=None`` for a life member's contribution-only authority, which
    renews no term and charges its contribution once a year.
    """

    class Meta:
        model = RenewalMandate

    user = factory.SubFactory(UserFactory)
    plan = factory.SubFactory(MembershipPlanFactory)
    contribution_cents = 0
    provider = PaymentProvider.MOCK
    method_ref = "mock"
    method_brand = "visa"
    method_last4 = "4242"
    method_exp_month = 12
    method_exp_year = 2030
    method_label = "Test card ending 4242, expires 12/2030"
    status = MandateStatus.ACTIVE


class RenewalAttemptFactory(ModelFactory[RenewalAttempt]):
    """Builds a scheduled attempt for today against a new mandate and membership.

    The mandate and the membership are independent new records unless both are
    passed, so a test that wants one member's own renewal gives both.
    """

    class Meta:
        model = RenewalAttempt

    mandate = factory.SubFactory(RenewalMandateFactory)
    membership = factory.SubFactory(MembershipFactory)
    scheduled_on = factory.LazyFunction(timezone.localdate)
