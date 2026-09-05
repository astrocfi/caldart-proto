"""factory_boy factories for every CalDART model (PLAN §15)."""

from __future__ import annotations

from datetime import timedelta

import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
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

User = get_user_model()

DEFAULT_PASSWORD = "test-password-123"  # noqa: S105 - test fixture


class GroupFactory(DjangoModelFactory):
    class Meta:
        model = Group
        django_get_or_create = ["name"]

    name = MEMBER


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ["email"]
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.test")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        if not create:
            return
        obj.set_password(extracted or DEFAULT_PASSWORD)
        obj.save(update_fields=["password"])

    @factory.post_generation
    def roles(obj, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for slug in extracted:
            obj.add_role(slug)


class DartFactory(DjangoModelFactory):
    class Meta:
        model = Dart
        django_get_or_create = ["name"]

    name = factory.Sequence(lambda n: f"Test DART {n}")
    airport_identifier = factory.Sequence(lambda n: f"T{n:02d}")
    city = factory.Faker("city")
    is_active = True
    sort_order = factory.Sequence(lambda n: n)


class AircraftFactory(DjangoModelFactory):
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


class MemberProfileFactory(DjangoModelFactory):
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


class MembershipPlanFactory(DjangoModelFactory):
    class Meta:
        model = MembershipPlan
        django_get_or_create = ["slug"]

    name = "Annual"
    slug = "annual"
    price_cents = 4_500
    duration_days = 365
    is_active = True
    sort_order = 1


class LifetimePlanFactory(MembershipPlanFactory):
    name = "Life"
    slug = "life"
    price_cents = 65_000
    duration_days = None
    sort_order = 2


class PaymentFactory(DjangoModelFactory):
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


class MembershipFactory(DjangoModelFactory):
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


class ReminderLogFactory(DjangoModelFactory):
    class Meta:
        model = ReminderLog

    user = factory.SubFactory(UserFactory)
    membership = factory.SubFactory(MembershipFactory)
    kind = ReminderKind.T30
    sent_at = factory.LazyFunction(timezone.now)
    to_email = factory.LazyAttribute(lambda o: o.user.email)


def make_home_page(title: str = "Home"):
    """Create a Wagtail ``HomePage`` under the tree root and return it."""
    from wagtail.models import Page

    from apps.cms.models import HomePage

    existing = HomePage.objects.first()
    if existing is not None:
        return existing
    root = Page.get_first_root_node()
    home = HomePage(title=title, slug="home")
    root.add_child(instance=home)
    home.save_revision().publish()
    return home


def make_site_settings(**kwargs):
    """Create or update the ``SiteSettings`` row for the default site."""
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
    return obj
