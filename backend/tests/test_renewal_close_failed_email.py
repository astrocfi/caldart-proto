"""A renewal charge a treasurer closes as failed emails the member once, after the commit.

``docs/developer/renewals.rst`` (charges a treasurer settles) and
``docs/developer/api-renewals.rst`` (``POST /admin/renewals/attempts/{id}/settle``) are
the contract.  A charge held for checking is built directly, with its payment sent and
unanswered, so closing it doesn't ask a provider anything.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import pytest
from django.core.mail import EmailMessage
from django.utils import timezone
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MembershipPlan, MembershipStatusChoices
from apps.payments.api.serializers import CLOSED_CHARGE_MEMBER_MESSAGE
from apps.payments.models import (
    MandateStatus,
    PaymentProvider,
    RenewalAttempt,
    RenewalMandate,
)
from apps.payments.renewals import emails as renewal_emails
from apps.payments.renewals.charge import (
    CLOSED_BY_TREASURER_MESSAGE,
    SETTLE_FAILED,
    settle_in_doubt,
)
from tests.conftest import Golden
from tests.factories import (
    MemberProfileFactory,
    MembershipFactory,
    PaymentFactory,
    RenewalAttemptFactory,
    RenewalMandateFactory,
)

pytestmark = pytest.mark.django_db

#: Why the scan held the charge, as it would record it.
HELD_REASON = "PayPal did not answer the charge."

#: The member's phone number on their profile.
MEMBER_PHONE = "415-555-0142"

#: Words the member's email never uses: the hold and the provider are the treasurer's.
INTERNAL_WORDS = ("in doubt", "PayPal", "provider", "treasurer", "Closed by")


def settle_url(attempt_id: int) -> str:
    """Where the treasurer settles a charge held for checking."""
    return f"/api/v1/admin/renewals/attempts/{attempt_id}/settle"


def held_charge(
    user: User,
    plan: MembershipPlan | None,
    *,
    ends_on: date | None,
    contribution_cents: int = 0,
) -> RenewalAttempt:
    """``user``'s PayPal charge held for checking, against a term ending ``ends_on``.

    ``plan=None`` makes it a recurring donation, which doesn't renew a term.
    """
    term = (
        MembershipFactory(
            user=user,
            plan=plan,
            starts_on=(ends_on or timezone.localdate()) - timedelta(days=364),
            ends_on=ends_on,
            status=MembershipStatusChoices.ACTIVE,
        )
        if plan is not None
        else None
    )
    mandate = RenewalMandateFactory(
        user=user,
        plan=plan,
        contribution_cents=contribution_cents,
        provider=PaymentProvider.PAYPAL,
        method_ref="vault_1",
        method_label="PayPal account r***@example.test",
    )
    payment = PaymentFactory(
        user=user,
        plan=plan,
        provider=PaymentProvider.PAYPAL,
        charge_sent_at=timezone.now(),
    )
    attempt: RenewalAttempt = RenewalAttemptFactory(
        mandate=mandate,
        membership=term,
        payment=payment,
        in_doubt=True,
        error=HELD_REASON,
    )
    return attempt


def close_as_failed(client: APIClient, attempt: RenewalAttempt) -> None:
    """Answer the charge with ``Close as failed``, as the Settle panel does."""
    response = client.post(settle_url(attempt.pk), {"outcome": "failed"}, format="json")
    assert response.status_code == 200


def subjects(outbox: list[EmailMessage]) -> list[str]:
    """Every subject in ``outbox``, without the organization's name before it."""
    return [str(message.subject).split(": ", 1)[1] for message in outbox]


def written(day: date) -> str:
    """``day`` as an email body writes it, such as *October 25, 2026*."""
    return f"{day:%B} {day.day}, {day.year}"


@pytest.fixture
def renewal(member: User, annual_plan: MembershipPlan, today: date) -> RenewalAttempt:
    """The member's renewal charge held for checking, their term running ten more days."""
    return held_charge(member, annual_plan, ends_on=today + timedelta(days=10))


# --------------------------------------------------------------------------
# The email
# --------------------------------------------------------------------------
def test_closing_a_charge_as_failed_emails_the_member_once(
    treasurer_client: APIClient,
    member: User,
    renewal: RenewalAttempt,
    mailoutbox: list[EmailMessage],
) -> None:
    """One message, to the member whose charge it was."""
    close_as_failed(treasurer_client, renewal)

    assert [message.to for message in mailoutbox] == [[member.email]]


def test_the_closed_charge_email_says_the_renewal_could_not_be_completed(
    treasurer_client: APIClient, renewal: RenewalAttempt, mailoutbox: list[EmailMessage]
) -> None:
    """The subject is the one every renewal that didn't go through carries."""
    close_as_failed(treasurer_client, renewal)

    assert subjects(mailoutbox) == ["we could not renew your membership"]


def test_the_closed_charge_email_reads_as_written(
    treasurer_client: APIClient,
    renewal: RenewalAttempt,
    today: date,
    mailoutbox: list[EmailMessage],
    golden: Golden,
) -> None:
    """The plain-text body matches its golden file exactly."""
    close_as_failed(treasurer_client, renewal)

    ends_on = today + timedelta(days=10)
    golden("renewal-closed.txt", str(mailoutbox[0].body), replace={written(ends_on): "<ENDS>"})


def test_the_closed_charge_email_says_automatic_renewal_is_paused(
    treasurer_client: APIClient, renewal: RenewalAttempt, mailoutbox: list[EmailMessage]
) -> None:
    """The member learns they won't be charged automatically."""
    close_as_failed(treasurer_client, renewal)

    assert "Automatic renewal is paused, so you won't be charged automatically." in " ".join(
        str(mailoutbox[0].body).split()
    )


def test_the_closed_charge_email_names_the_day_the_membership_ends(
    treasurer_client: APIClient,
    renewal: RenewalAttempt,
    today: date,
    mailoutbox: list[EmailMessage],
) -> None:
    """A term still running is named by the day it runs until."""
    close_as_failed(treasurer_client, renewal)

    body = " ".join(str(mailoutbox[0].body).split())
    assert f"Your membership runs until {written(today + timedelta(days=10))}." in body


def test_the_closed_charge_email_says_a_membership_has_ended(
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
) -> None:
    """A term that has already run out is named by the day it ended."""
    ended_on = today - timedelta(days=3)
    close_as_failed(treasurer_client, held_charge(member, annual_plan, ends_on=ended_on))

    body = " ".join(str(mailoutbox[0].body).split())
    assert f"Your membership ended on {written(ended_on)}." in body


@pytest.mark.parametrize(
    "url",
    [renewal_emails.renew_url, renewal_emails.payments_url],
    ids=["renew-by-hand", "turn-it-back-on"],
)
def test_the_closed_charge_email_links_the_screens_that_put_it_right(
    treasurer_client: APIClient,
    renewal: RenewalAttempt,
    mailoutbox: list[EmailMessage],
    url: Callable[[], str],
) -> None:
    """The member is shown where to renew by hand and where to turn renewal back on."""
    close_as_failed(treasurer_client, renewal)

    assert url() in str(mailoutbox[0].body)


@pytest.mark.parametrize("word", INTERNAL_WORDS)
def test_the_closed_charge_email_never_speaks_of_the_hold(
    treasurer_client: APIClient,
    renewal: RenewalAttempt,
    mailoutbox: list[EmailMessage],
    word: str,
) -> None:
    """Neither the text nor the HTML names the hold, the provider, or who closed it."""
    close_as_failed(treasurer_client, renewal)

    message = mailoutbox[0]
    html = str(message.alternatives[0][0])  # type: ignore[attr-defined]  # EmailMultiAlternatives
    assert word not in f"{message.body}\n{html}"


def test_the_closed_charge_email_is_logged_as_a_failed_charge(
    treasurer_client: APIClient, renewal: RenewalAttempt, mailoutbox: list[EmailMessage]
) -> None:
    """The send is stamped on the attempt, as a decline's notice is."""
    close_as_failed(treasurer_client, renewal)

    assert RenewalAttempt.objects.get(pk=renewal.pk).result_emailed_at is not None


# --------------------------------------------------------------------------
# A recurring donation
# --------------------------------------------------------------------------
@pytest.fixture
def donation(member: User, life_plan: MembershipPlan) -> RenewalAttempt:
    """A life member's recurring donation of $25.00 a year, held for checking."""
    MembershipFactory(
        user=member, plan=life_plan, ends_on=None, status=MembershipStatusChoices.ACTIVE
    )
    return held_charge(member, None, ends_on=None, contribution_cents=2500)


def test_a_closed_donation_says_the_recurring_donation_could_not_be_taken(
    treasurer_client: APIClient, donation: RenewalAttempt, mailoutbox: list[EmailMessage]
) -> None:
    """A life member's donation carries the donation subject."""
    close_as_failed(treasurer_client, donation)

    assert subjects(mailoutbox) == ["we could not take your recurring donation"]


def test_a_closed_donation_reads_as_written(
    treasurer_client: APIClient,
    donation: RenewalAttempt,
    mailoutbox: list[EmailMessage],
    golden: Golden,
) -> None:
    """The donation's plain-text body matches its golden file exactly."""
    close_as_failed(treasurer_client, donation)

    golden("renewal-closed-donation.txt", str(mailoutbox[0].body))


def test_a_closed_donation_never_speaks_of_renewing(
    treasurer_client: APIClient, donation: RenewalAttempt, mailoutbox: list[EmailMessage]
) -> None:
    """A donation doesn't renew anything, so its email never says it does."""
    close_as_failed(treasurer_client, donation)

    assert "renew" not in str(mailoutbox[0].body).lower()


# --------------------------------------------------------------------------
# A renewal with a contribution
# --------------------------------------------------------------------------
@pytest.fixture
def renewal_and_contribution(
    member: User, annual_plan: MembershipPlan, today: date
) -> RenewalAttempt:
    """The member's renewal with a $20.00 contribution, held for checking."""
    return held_charge(
        member, annual_plan, ends_on=today + timedelta(days=10), contribution_cents=2000
    )


def test_a_closed_renewal_and_contribution_carries_the_renewal_subject(
    treasurer_client: APIClient,
    renewal_and_contribution: RenewalAttempt,
    mailoutbox: list[EmailMessage],
) -> None:
    """Dues and a contribution together are a renewal, as every renewal email says."""
    close_as_failed(treasurer_client, renewal_and_contribution)

    assert subjects(mailoutbox) == ["we could not renew your membership"]


def test_a_closed_renewal_and_contribution_names_both(
    treasurer_client: APIClient,
    annual_plan: MembershipPlan,
    renewal_and_contribution: RenewalAttempt,
    mailoutbox: list[EmailMessage],
) -> None:
    """The body says the renewal and the contribution couldn't be completed."""
    close_as_failed(treasurer_client, renewal_and_contribution)

    body = " ".join(str(mailoutbox[0].body).split())
    assert (
        "We couldn't complete the automatic renewal of your "
        f"{annual_plan.name} membership and your contribution."
    ) in body


# --------------------------------------------------------------------------
# What the member reads on My payments afterwards
# --------------------------------------------------------------------------
def my_renewal(client: APIClient, member: User) -> dict[str, object]:
    """The member's own renewal, as My payments reads it."""
    client.force_login(member)
    mandate: dict[str, object] = client.get("/api/v1/me/renewal").json()["mandate"]
    return mandate


def test_the_member_reads_a_closed_charge_in_the_emails_words(
    treasurer_client: APIClient, member: User, renewal: RenewalAttempt
) -> None:
    """My payments says the last charge couldn't be completed, as the email does."""
    close_as_failed(treasurer_client, renewal)

    assert my_renewal(treasurer_client, member)["last_error"] == CLOSED_CHARGE_MEMBER_MESSAGE


def test_the_member_is_told_the_last_charge_was_closed(
    treasurer_client: APIClient, member: User, renewal: RenewalAttempt
) -> None:
    """``last_charge_closed`` lets My payments drop the words for a refusal."""
    close_as_failed(treasurer_client, renewal)

    assert my_renewal(treasurer_client, member)["last_charge_closed"] is True


def test_the_treasurer_reads_what_the_closed_charge_recorded(
    treasurer_client: APIClient, renewal: RenewalAttempt
) -> None:
    """The finance screens keep the attempt's own record of who closed it."""
    close_as_failed(treasurer_client, renewal)

    response = treasurer_client.get(f"/api/v1/admin/renewals/{renewal.mandate_id}")

    assert response.json()["last_error"] == CLOSED_BY_TREASURER_MESSAGE


# --------------------------------------------------------------------------
# When it goes, and when it doesn't
# --------------------------------------------------------------------------
def test_the_closed_charge_email_waits_for_the_commit(
    treasurer: User,
    renewal: RenewalAttempt,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """Settled outside a request, the email waits for the commit and isn't sent before."""
    with django_capture_on_commit_callbacks(execute=False):
        settle_in_doubt(renewal.pk, outcome=SETTLE_FAILED, actor=treasurer)

    assert mailoutbox == []


def test_the_closed_charge_email_goes_once_the_commit_comes(
    treasurer: User,
    renewal: RenewalAttempt,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The queued email is the member's one message."""
    with django_capture_on_commit_callbacks(execute=True):
        settle_in_doubt(renewal.pk, outcome=SETTLE_FAILED, actor=treasurer)

    assert subjects(mailoutbox) == ["we could not renew your membership"]


def test_the_closed_charge_email_is_handed_to_the_caller_to_send(
    treasurer: User,
    renewal: RenewalAttempt,
    mailoutbox: list[EmailMessage],
) -> None:
    """Given ``defer``, the settle hands it the email and doesn't send it itself."""
    deferred: list[object] = []

    settle_in_doubt(renewal.pk, outcome=SETTLE_FAILED, actor=treasurer, defer=deferred.append)

    assert len(deferred) == 1
    assert mailoutbox == []


@pytest.mark.usefixtures("refusing_mail_server")
def test_a_refused_email_leaves_the_charge_closed(
    treasurer_client: APIClient, renewal: RenewalAttempt
) -> None:
    """The settlement stands whatever the mail server says."""
    response = treasurer_client.post(settle_url(renewal.pk), {"outcome": "failed"}, format="json")

    assert response.status_code == 200
    assert RenewalMandate.objects.get().status == MandateStatus.PAUSED


@pytest.mark.usefixtures("refusing_mail_server")
def test_a_refused_email_is_not_stamped_as_sent(
    treasurer_client: APIClient, renewal: RenewalAttempt
) -> None:
    """An email that never went leaves the attempt's ``result_emailed_at`` unset."""
    close_as_failed(treasurer_client, renewal)

    assert RenewalAttempt.objects.get(pk=renewal.pk).result_emailed_at is None


def test_a_charge_whose_renewal_was_already_off_doesnt_email_the_member(
    treasurer_client: APIClient, renewal: RenewalAttempt, mailoutbox: list[EmailMessage]
) -> None:
    """A renewal the member turned off isn't paused, so they aren't emailed."""
    RenewalMandate.objects.update(status=MandateStatus.CANCELED)

    close_as_failed(treasurer_client, renewal)

    assert mailoutbox == []


def test_releasing_a_charge_doesnt_email_the_member(
    treasurer_client: APIClient, renewal: RenewalAttempt, mailoutbox: list[EmailMessage]
) -> None:
    """*No payment found* leaves the charge to the next run, unannounced."""
    treasurer_client.post(settle_url(renewal.pk), {"outcome": "released"}, format="json")

    assert mailoutbox == []


# --------------------------------------------------------------------------
# What the treasurer is answered
# --------------------------------------------------------------------------
def test_the_answer_carries_the_members_email_address(
    treasurer_client: APIClient, member: User, renewal: RenewalAttempt
) -> None:
    """The treasurer is given the address to write to."""
    response = treasurer_client.post(settle_url(renewal.pk), {"outcome": "failed"}, format="json")

    assert response.json()["user_email"] == member.email


def test_the_answer_carries_the_members_phone_number(
    treasurer_client: APIClient, member: User, renewal: RenewalAttempt
) -> None:
    """The phone number on the member's profile is given beside it."""
    MemberProfileFactory(user=member, phone=MEMBER_PHONE)

    response = treasurer_client.post(settle_url(renewal.pk), {"outcome": "failed"}, format="json")

    assert response.json()["user_phone"] == MEMBER_PHONE


def test_the_answer_carries_a_blank_phone_for_a_member_without_one(
    treasurer_client: APIClient, renewal: RenewalAttempt
) -> None:
    """A member without a profile, or a number, is answered with an empty string."""
    response = treasurer_client.post(settle_url(renewal.pk), {"outcome": "failed"}, format="json")

    assert response.json()["user_phone"] == ""


def test_the_answer_says_the_member_is_emailed(
    treasurer_client: APIClient, renewal: RenewalAttempt
) -> None:
    """A close that paused the renewal tells the treasurer the member is told."""
    response = treasurer_client.post(settle_url(renewal.pk), {"outcome": "failed"}, format="json")

    assert response.json()["member_emailed"] is True


def test_the_answer_says_a_member_whose_renewal_was_off_is_not_emailed(
    treasurer_client: APIClient, renewal: RenewalAttempt
) -> None:
    """A close that didn't pause the renewal doesn't email the member, and says so."""
    RenewalMandate.objects.update(status=MandateStatus.CANCELED)

    response = treasurer_client.post(settle_url(renewal.pk), {"outcome": "failed"}, format="json")

    assert response.json()["member_emailed"] is False


def test_the_answer_to_a_release_says_the_member_isnt_emailed(
    treasurer_client: APIClient, renewal: RenewalAttempt
) -> None:
    """*No payment found* doesn't email the member yet."""
    response = treasurer_client.post(settle_url(renewal.pk), {"outcome": "released"}, format="json")

    assert response.json()["member_emailed"] is False


@pytest.mark.parametrize("field", ["user_email", "user_phone"])
def test_the_answer_to_a_release_leaves_out_the_contact_details(
    treasurer_client: APIClient, member: User, renewal: RenewalAttempt, field: str
) -> None:
    """Only a closed charge's answer gives the member's address and phone number."""
    MemberProfileFactory(user=member, phone=MEMBER_PHONE)

    response = treasurer_client.post(settle_url(renewal.pk), {"outcome": "released"}, format="json")

    assert response.json()[field] is None


def test_the_answer_says_the_renewal_is_paused(
    treasurer_client: APIClient, renewal: RenewalAttempt
) -> None:
    """A close that paused the renewal says it stands paused."""
    response = treasurer_client.post(settle_url(renewal.pk), {"outcome": "failed"}, format="json")

    assert response.json()["mandate_paused"] is True


def test_the_answer_says_the_renewal_is_paused_for_a_member_without_an_address(
    treasurer_client: APIClient, member: User, renewal: RenewalAttempt
) -> None:
    """The pause is reported whether or not the member could be emailed."""
    User.objects.filter(pk=member.pk).update(email="")

    response = treasurer_client.post(settle_url(renewal.pk), {"outcome": "failed"}, format="json")

    assert response.json()["mandate_paused"] is True


def test_the_answer_says_a_renewal_that_was_off_is_not_paused(
    treasurer_client: APIClient, renewal: RenewalAttempt
) -> None:
    """A renewal the member turned off stays off, and isn't called paused."""
    RenewalMandate.objects.update(status=MandateStatus.CANCELED)

    response = treasurer_client.post(settle_url(renewal.pk), {"outcome": "failed"}, format="json")

    assert response.json()["mandate_paused"] is False


def test_the_answer_to_a_release_doesnt_call_the_renewal_paused(
    treasurer_client: APIClient, renewal: RenewalAttempt
) -> None:
    """*No payment found* leaves the renewal on."""
    response = treasurer_client.post(settle_url(renewal.pk), {"outcome": "released"}, format="json")

    assert response.json()["mandate_paused"] is False


@pytest.mark.parametrize(
    ("plan_fixture", "kind"),
    [("annual_plan", "renewal"), (None, "contribution")],
    ids=["renewal", "donation"],
)
def test_every_charge_names_its_kind(
    treasurer_client: APIClient,
    member: User,
    request: pytest.FixtureRequest,
    today: date,
    plan_fixture: str | None,
    kind: str,
) -> None:
    """The charge list says whether each charge renews a membership or is a donation."""
    plan = request.getfixturevalue(plan_fixture) if plan_fixture is not None else None
    held_charge(member, plan, ends_on=today, contribution_cents=0 if plan else 2500)

    response = treasurer_client.get("/api/v1/admin/renewals/attempts")

    assert response.json()["results"][0]["mandate_kind"] == kind
