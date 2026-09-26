"""Members, friends, and donors: the kind of an account and what follows from it.

A member pays dues; a friend is a person with a portal account and no dues, who
is never current and never expired; a donor gives through the public site and
cannot sign in.  ``docs/user/getting-started.rst`` says what each kind of person
can do, and ``docs/developer/data-model.rst`` how the kind is stored and worked out.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, timedelta
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import MEMBER, ROLE_DESCRIPTIONS, USER_ADMIN
from apps.accounts.services import (
    create_account,
    make_reset_token,
    send_email_verification,
    send_password_invitation,
    send_password_reset_email,
)
from apps.cms.models import SiteSettings, StandardPage, members_wall_state
from apps.members import services as members_services
from apps.members.models import MemberProfile, MembershipPlan, MembershipState
from apps.members.services import (
    account_kind,
    activate_term,
    convert_due_friends,
    kind_annotation,
    membership_status,
    register_member,
)
from apps.payments.models import PaymentStatus
from apps.payments.services import create_checkout
from apps.reminders.services import send_renewal_reminders
from caldart import audit
from tests.conftest import (
    GOOD_PASSWORD,
    LOGIN_URL,
    ME_URL,
    REGISTER_URL,
    RESET_CONFIRM_URL,
    RESET_URL,
    audit_messages,
    register_payload,
)
from tests.factories import (
    DEFAULT_PASSWORD,
    MembershipFactory,
    PaymentFactory,
    UserFactory,
    expire_membership,
    grant_membership,
    make_standard_page,
)

if TYPE_CHECKING:
    # rest_framework.test.APIClient.post() is typed to return this class, but it
    # exists only in the stub: rest_framework monkey-patches Django's test response
    # at runtime rather than defining a real subclass.
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

pytestmark = pytest.mark.django_db

USERS_URL = "/api/v1/admin/users"
MEMBERS_URL = "/api/v1/admin/members"
MEMBERSHIP_URL = "/api/v1/me/membership"
MY_PAYMENTS_URL = "/api/v1/me/payments"
VERIFY_URL = "/api/v1/auth/email/verify"

TAKEN = "An account already uses that email address. Sign in, or reset your password."
DEACTIVATED_AT_REGISTER = "This email belongs to a deactivated account. Sign in to reactivate it."
WRONG_CREDENTIALS = "Incorrect email address or password."
INVALID_RESET_LINK = "That password reset link is invalid or has expired. Request a new one."

type OnCommit = DjangoCaptureOnCommitCallbacks


@pytest.fixture
def donor(db: None) -> User:
    """A donor: an account with no password, no role, and one settled gift."""
    user = create_account(
        email="giver@example.test", first_name="Gil", last_name="Ivers", kind=AccountKind.DONOR
    )
    PaymentFactory(user=user, plan=None, amount_cents=5_000, status=PaymentStatus.SUCCEEDED)
    return user


@pytest.fixture
def pending_friend(member: User, annual_plan: MembershipPlan, today: date) -> User:
    """A current member who has asked to become a friend once the term runs out."""
    term = grant_membership(member, annual_plan, days_left=20)
    assert term.ends_on is not None
    member.friend_on = term.ends_on + timedelta(days=1)
    member.save(update_fields=["friend_on"])
    return member


@pytest.fixture
def signed_in(api_client: APIClient) -> Callable[[User], APIClient]:
    """Sign ``user`` in on the shared API client and return the client."""

    def sign_in(user: User) -> APIClient:
        api_client.force_login(user)
        return api_client

    return sign_in


# --------------------------------------------------------------------------
# The kind on the account
# --------------------------------------------------------------------------
def test_the_three_kinds_and_their_labels() -> None:
    """``AccountKind`` offers member, friend, and donor, in that order."""
    assert AccountKind.choices == [
        ("member", "Member"),
        ("friend", "Friend"),
        ("donor", "Donor"),
    ]


def test_a_new_account_is_a_member_with_no_pending_change(db: None) -> None:
    """An account created without a kind is a member, with no ``friend_on`` date."""
    user = create_account(email="plain@example.test", password=GOOD_PASSWORD)
    assert user.kind == AccountKind.MEMBER
    assert user.friend_on is None


@pytest.mark.parametrize(
    ("kind", "roles"),
    [
        (AccountKind.MEMBER, [MEMBER]),
        (AccountKind.FRIEND, [MEMBER]),
        (AccountKind.DONOR, []),
    ],
    ids=["member", "friend", "donor"],
)
def test_create_account_gives_the_member_role_to_members_and_friends_only(
    db: None, kind: AccountKind, roles: list[str]
) -> None:
    """Members and friends hold the ``member`` role; a donor holds no role at all."""
    user = create_account(email=f"{kind}@example.test", kind=kind)
    assert user.kind == kind
    assert user.roles == roles


def test_the_member_role_describes_members_and_friends() -> None:
    """The ``member`` role's description names both kinds of person who hold it."""
    assert ROLE_DESCRIPTIONS[MEMBER] == "A member or a friend with a portal account."


# --------------------------------------------------------------------------
# The effective kind, in Python and in SQL
# --------------------------------------------------------------------------
def _kind_cases(today: date) -> dict[str, User]:
    """One account per case the two statements of the kind rule must agree on."""
    day = timedelta(days=1)
    return {
        "member": UserFactory(email="k-member@example.test"),
        "friend": UserFactory(email="k-friend@example.test", kind=AccountKind.FRIEND),
        "donor": UserFactory(email="k-donor@example.test", kind=AccountKind.DONOR),
        "due-yesterday": UserFactory(email="k-due1@example.test", friend_on=today - day),
        "due-today": UserFactory(email="k-due0@example.test", friend_on=today),
        "due-tomorrow": UserFactory(email="k-due2@example.test", friend_on=today + day),
    }


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("member", AccountKind.MEMBER),
        ("friend", AccountKind.FRIEND),
        ("donor", AccountKind.DONOR),
        ("due-yesterday", AccountKind.FRIEND),
        ("due-today", AccountKind.FRIEND),
        ("due-tomorrow", AccountKind.MEMBER),
    ],
)
def test_account_kind_counts_a_due_conversion_as_a_friend(
    today: date, label: str, expected: AccountKind
) -> None:
    """A member whose ``friend_on`` has arrived is a friend already; one ahead is not."""
    assert account_kind(_kind_cases(today)[label], today) == expected


def test_kind_annotation_agrees_with_account_kind(today: date) -> None:
    """The SQL statement of the rule gives every account the kind the Python one does."""
    cases = _kind_cases(today)
    annotated = dict(
        User.objects.filter(pk__in=[user.pk for user in cases.values()])
        .annotate(effective=kind_annotation(today))
        .values_list("pk", "effective")
    )
    for label, user in cases.items():
        assert annotated[user.pk] == account_kind(user, today), label


def test_convert_due_friends_writes_down_every_due_conversion(today: date) -> None:
    """A due member becomes a friend with no pending date; one ahead is untouched."""
    cases = _kind_cases(today)
    converted = convert_due_friends(today)
    assert converted == 2
    for label in ("due-yesterday", "due-today"):
        cases[label].refresh_from_db()
        assert (cases[label].kind, cases[label].friend_on) == (AccountKind.FRIEND, None), label
    cases["due-tomorrow"].refresh_from_db()
    assert cases["due-tomorrow"].kind == AccountKind.MEMBER


def test_convert_due_friends_records_each_conversion(
    audit_log: pytest.LogCaptureFixture, today: date
) -> None:
    """Every conversion is an ``account.kind`` audit line naming the new kind."""
    user = UserFactory(email="due@example.test", friend_on=today)
    convert_due_friends(today)
    assert audit_messages(audit_log) == [
        f"action={audit.ACCOUNT_KIND} actor=command target={user.pk} to=friend "
        f"on={today.isoformat()}"
    ]


def test_convert_due_friends_leaves_a_member_who_paid_after_the_list_was_read(
    monkeypatch: pytest.MonkeyPatch, audit_log: pytest.LogCaptureFixture, today: date
) -> None:
    """A payment that lands between the read and the write keeps the member a member."""
    user = UserFactory(email="due@example.test", friend_on=today)
    listed = members_services.due_conversions

    def listed_then_paid(day: date) -> list[User]:
        due = listed(day)
        User.objects.filter(pk=user.pk).update(kind=AccountKind.MEMBER, friend_on=None)
        return due

    monkeypatch.setattr(members_services, "due_conversions", listed_then_paid)
    assert convert_due_friends(today) == 0
    user.refresh_from_db()
    assert user.kind == AccountKind.MEMBER
    assert audit_messages(audit_log) == []


def test_the_reminder_run_writes_down_due_conversions(today: date) -> None:
    """The daily reminder run converts the members whose ``friend_on`` has come."""
    user = UserFactory(email="due@example.test", friend_on=today)
    send_renewal_reminders(today=today)
    user.refresh_from_db()
    assert user.kind == AccountKind.FRIEND


def test_a_dry_reminder_run_converts_nobody(today: date) -> None:
    """A rehearsal of the reminder run writes no conversion down."""
    user = UserFactory(email="due@example.test", friend_on=today)
    send_renewal_reminders(today=today, dry_run=True)
    user.refresh_from_db()
    assert user.kind == AccountKind.MEMBER


def test_friends_are_never_sent_renewal_reminders(
    friend: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A friend whose old term ran out today is not told so; a member likewise is."""
    control = UserFactory(email="control@example.test", roles=[MEMBER])
    expire_membership(control, annual_plan, days_ago=0)
    expire_membership(friend, annual_plan, days_ago=0)
    run = send_renewal_reminders(today=today)
    assert [action.email for action in run.actions] == [control.email]


def test_a_pending_friend_is_never_sent_renewal_reminders(
    pending_friend: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A member who asked to become a friend is not nagged about the term running out."""
    control = UserFactory(email="control@example.test", roles=[MEMBER])
    grant_membership(control, annual_plan, days_left=20)
    run = send_renewal_reminders(today=today)
    assert [action.email for action in run.actions] == [control.email]


# --------------------------------------------------------------------------
# Membership state
# --------------------------------------------------------------------------
def test_a_friend_reads_as_friend_with_nothing_to_expire(friend: User) -> None:
    """A friend's status is ``friend``, with no date, no plan, and never lifetime."""
    assert membership_status(friend) == {
        "status": MembershipState.FRIEND,
        "expires_on": None,
        "plan": None,
        "is_lifetime": False,
    }


def test_a_friends_past_terms_never_make_them_expired(
    friend: User, annual_plan: MembershipPlan
) -> None:
    """A friend who was once a member is a friend, not a lapsed member."""
    expire_membership(friend, annual_plan)
    assert membership_status(friend)["status"] == MembershipState.FRIEND


def test_a_pending_friend_is_current_until_the_day_comes(pending_friend: User) -> None:
    """Until ``friend_on`` arrives the member's paid term still counts."""
    assert membership_status(pending_friend)["status"] == MembershipState.CURRENT


def test_a_pending_friend_is_a_friend_from_the_day(pending_friend: User) -> None:
    """On ``friend_on`` itself the member reads as a friend."""
    assert pending_friend.friend_on is not None
    status = membership_status(pending_friend, pending_friend.friend_on)
    assert status["status"] == MembershipState.FRIEND


def test_friend_is_a_membership_state() -> None:
    """``MembershipState`` gains ``friend``, after the four it had."""
    assert MembershipState.FRIEND.label == "Friend"


# --------------------------------------------------------------------------
# Members-only content
# --------------------------------------------------------------------------
@pytest.fixture
def walled_page(site_settings: SiteSettings) -> StandardPage:
    """A published, members-only standard page holding one secret paragraph."""
    home = site_settings.site.root_page.specific
    return make_standard_page(
        home,
        "members",
        "Members",
        members_only=True,
        body=[("paragraph", "<p>The secret handbook.</p>")],
    )


def test_a_friend_is_refused_members_only_content(friend: User) -> None:
    """A friend with no staff role may not read members-only pages."""
    assert friend.can_access_members_content is False


def test_a_friend_with_a_staff_role_keeps_its_powers(friend: User) -> None:
    """A friend who is also a user administrator reads members-only pages."""
    friend.add_role(USER_ADMIN)
    assert friend.can_access_members_content is True


def test_the_wall_state_for_a_friend_is_friend(friend: User) -> None:
    """The wall answers a signed-in friend with its own state."""
    assert members_wall_state(friend) == "friend"


def test_the_wall_invites_a_friend_to_become_a_member(
    client: Client, walled_page: StandardPage, friend: User
) -> None:
    """A friend sees the wall's friend sentence and a Make me a member link."""
    client.force_login(friend)
    response = client.get(walled_page.url)
    body = response.content.decode()
    assert response.status_code == 403
    assert "Friends of CalDART can read this page by becoming a member." in body
    assert 'href="/portal/membership/join"' in body
    assert "Make me a member" in body


# --------------------------------------------------------------------------
# Terms and checkout
# --------------------------------------------------------------------------
def test_a_term_for_a_friend_makes_them_a_member(friend: User, annual_plan: MembershipPlan) -> None:
    """Paying dues, or a manual grant, is what makes a friend a member."""
    activate_term(friend, annual_plan)
    friend.refresh_from_db()
    assert friend.kind == AccountKind.MEMBER


def test_a_term_records_the_change_of_kind(
    friend: User, annual_plan: MembershipPlan, audit_log: pytest.LogCaptureFixture
) -> None:
    """The friend's return to membership is an ``account.kind`` audit line."""
    activate_term(friend, annual_plan)
    assert f"action={audit.ACCOUNT_KIND} actor=command target={friend.pk} to=member" in (
        audit_messages(audit_log)
    )


def test_a_term_for_a_pending_friend_cancels_the_pending_change(
    pending_friend: User, annual_plan: MembershipPlan
) -> None:
    """A member who pays again while a conversion is pending stays a member."""
    activate_term(pending_friend, annual_plan)
    pending_friend.refresh_from_db()
    assert pending_friend.friend_on is None


def test_a_term_leaves_a_members_kind_alone(member: User, annual_plan: MembershipPlan) -> None:
    """A member who renews is still a member."""
    activate_term(member, annual_plan)
    member.refresh_from_db()
    assert member.kind == AccountKind.MEMBER


def test_a_friend_can_check_out_a_plan(friend: User, annual_plan: MembershipPlan) -> None:
    """A friend may buy a plan, which the checkout prices like anybody else's."""
    payment = create_checkout(friend, annual_plan.slug)
    assert payment.plan_amount_cents == annual_plan.price_cents


# --------------------------------------------------------------------------
# The user payload
# --------------------------------------------------------------------------
def test_the_user_payload_carries_the_kind_and_the_pending_date(
    signed_in: Callable[[User], APIClient], pending_friend: User
) -> None:
    """``/auth/me`` answers the stored ``kind`` and the pending ``friend_on``."""
    body = signed_in(pending_friend).get(ME_URL).json()
    assert (body["kind"], body["friend_on"]) == ("member", str(pending_friend.friend_on))


def test_me_membership_answers_friend_for_a_friend(
    signed_in: Callable[[User], APIClient], friend: User
) -> None:
    """``/me/membership`` reports a friend's state as ``friend``."""
    assert signed_in(friend).get(MEMBERSHIP_URL).json()["status"] == "friend"


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("posted", "stored"),
    [({}, "member"), ({"kind": "member"}, "member"), ({"kind": "friend"}, "friend")],
    ids=["default", "member", "friend"],
)
def test_register_stores_the_chosen_kind(
    api_client: APIClient, posted: dict[str, str], stored: str
) -> None:
    """``POST /auth/register`` takes ``kind``, a member unless it says friend."""
    response = api_client.post(REGISTER_URL, register_payload(**posted), format="json")
    assert response.status_code == 201
    assert response.json()["kind"] == stored


def test_a_friend_who_registers_holds_the_member_role(api_client: APIClient) -> None:
    """A friend is given the same ``member`` role a member is."""
    response = api_client.post(REGISTER_URL, register_payload(kind="friend"), format="json")
    assert response.json()["roles"] == ["member"]


def test_register_refuses_to_make_a_donor(api_client: APIClient) -> None:
    """Nobody registers as a donor: that kind comes from giving on the public site."""
    response = api_client.post(REGISTER_URL, register_payload(kind="donor"), format="json")
    assert response.status_code == 400
    assert response.json() == {"kind": ['"donor" is not a valid choice.']}


def _verification_token() -> str:
    """The ``token`` of the one verification link in the outbox."""
    [message] = mail.outbox
    match = re.search(r"/portal/verify-email\?token=(\S+)", str(message.body))
    assert match, f"no verification link in:\n{message.body}"
    return match.group(1)


@pytest.fixture
def donor_registration(
    api_client: APIClient, donor: User, django_capture_on_commit_callbacks: OnCommit
) -> ApiResponse:
    """Somebody registers as a friend with the donor's address, not yet proving it."""
    payload = register_payload(email="GIVER@example.test", kind="friend")
    with django_capture_on_commit_callbacks(execute=True):
        return api_client.post(REGISTER_URL, payload, format="json")


@pytest.fixture
def upgraded_donor(donor: User, donor_registration: ApiResponse) -> User:
    """The donor, once the verification link mailed at registration is followed."""
    Client().post(VERIFY_URL, {"token": _verification_token()}, content_type="application/json")
    donor.refresh_from_db()
    return donor


def test_registering_a_donors_address_asks_for_the_address_to_be_proved(
    donor: User, donor_registration: ApiResponse
) -> None:
    """The answer is a 202 naming the address the link went to, not a signed-in user."""
    assert donor_registration.status_code == 202
    assert donor_registration.json() == {
        "detail": "Verification message sent to giver@example.test."
    }


def test_registering_a_donors_address_signs_nobody_in(
    api_client: APIClient, donor_registration: ApiResponse
) -> None:
    """Whoever registered is not signed in, so the donor's gifts stay out of reach."""
    assert api_client.get(MY_PAYMENTS_URL).status_code == 401


def test_a_donor_upgrade_cannot_sign_in_before_the_address_is_proved(
    api_client: APIClient, donor: User, donor_registration: ApiResponse
) -> None:
    """The password chosen at registration opens nothing until the link is followed."""
    response = api_client.post(
        LOGIN_URL, {"email": donor.email, "password": GOOD_PASSWORD}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"detail": WRONG_CREDENTIALS}


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("kind", AccountKind.DONOR),
        ("first_name", "Gil"),
        ("last_name", "Ivers"),
        ("roles", []),
    ],
)
def test_registering_a_donors_address_leaves_the_donor_as_it_was(
    donor: User, donor_registration: ApiResponse, field: str, expected: object
) -> None:
    """Until the address is proved, the kind, the names, and the roles are untouched."""
    donor.refresh_from_db()
    assert getattr(donor, field) == expected


def test_the_upgraded_donor_keeps_the_gifts(upgraded_donor: User) -> None:
    """Following the link upgrades the donor in place, keeping the gifts made so far."""
    assert upgraded_donor.payments.count() == 1


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("kind", AccountKind.FRIEND),
        ("first_name", "Nora"),
        ("last_name", "Bright"),
        ("roles", [MEMBER]),
        ("email_verified", True),
    ],
)
def test_the_upgraded_donor_takes_what_the_form_gave(
    upgraded_donor: User, field: str, expected: object
) -> None:
    """The link writes the kind, the names, and the role, and proves the address."""
    assert getattr(upgraded_donor, field) == expected


def test_the_upgraded_donor_signs_in_with_the_new_password(
    api_client: APIClient, upgraded_donor: User
) -> None:
    """Once the address is proved, the password chosen at registration signs in."""
    response = api_client.post(
        LOGIN_URL, {"email": upgraded_donor.email, "password": GOOD_PASSWORD}, format="json"
    )
    assert response.status_code == 200


def test_the_donor_upgrade_is_mailed_to_the_donors_address(
    donor: User, donor_registration: ApiResponse
) -> None:
    """The registration mails one verification link, to the address the donor holds."""
    assert [message.to for message in mail.outbox] == [[donor.email]]


def test_the_upgraded_donor_gets_a_profile(donor: User, donor_registration: ApiResponse) -> None:
    """The join wizard patches ``/me/profile``, so the upgraded account has one."""
    assert MemberProfile.objects.filter(user=donor).exists()


def test_register_still_refuses_a_members_address(api_client: APIClient, member: User) -> None:
    """An address that belongs to an active member or friend is taken."""
    response = api_client.post(REGISTER_URL, register_payload(email=member.email), format="json")
    assert response.status_code == 400
    assert response.json() == {"email": [TAKEN]}


def test_register_refuses_a_deactivated_address_with_a_code(
    api_client: APIClient, member: User
) -> None:
    """A deactivated account's address is refused with the ``deactivated`` code."""
    member.is_active = False
    member.save(update_fields=["is_active"])
    response = api_client.post(
        REGISTER_URL, register_payload(email=member.email.upper()), format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"email": [DEACTIVATED_AT_REGISTER], "code": "deactivated"}


def test_register_member_with_a_kind_creates_that_kind(db: None) -> None:
    """``register_member`` stores the kind it is given."""
    user = register_member(email="f@example.test", password=GOOD_PASSWORD, kind=AccountKind.FRIEND)
    assert user.kind == AccountKind.FRIEND


# --------------------------------------------------------------------------
# Donors cannot sign in or set a password
# --------------------------------------------------------------------------
def test_a_donor_cannot_sign_in(api_client: APIClient, donor: User) -> None:
    """Login answers a donor with the generic refusal, even with a password set."""
    donor.set_password(DEFAULT_PASSWORD)
    donor.save(update_fields=["password"])
    response = api_client.post(
        LOGIN_URL, {"email": donor.email, "password": DEFAULT_PASSWORD}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"detail": WRONG_CREDENTIALS}


def test_a_donor_is_sent_no_password_reset(donor: User) -> None:
    """``send_password_reset_email`` skips a donor and says so."""
    assert send_password_reset_email(donor) is False
    assert mail.outbox == []


def test_the_reset_endpoint_mails_a_donor_nothing(api_client: APIClient, donor: User) -> None:
    """``POST /auth/password/reset`` answers 204 for a donor and sends nothing."""
    response = api_client.post(RESET_URL, {"email": donor.email}, format="json")
    assert response.status_code == 204
    assert mail.outbox == []


def test_a_donor_is_sent_no_invitation(donor: User) -> None:
    """``send_password_invitation`` sends a donor nothing."""
    send_password_invitation(donor)
    assert mail.outbox == []


def test_a_donor_is_sent_no_verification_message(donor: User) -> None:
    """``send_email_verification`` sends a donor nothing."""
    send_email_verification(donor)
    assert mail.outbox == []


def test_a_reset_link_for_a_donor_is_refused(api_client: APIClient, donor: User) -> None:
    """A reset link naming a donor's account is as unusable as a forged one."""
    uid, token = make_reset_token(donor)
    assert default_token_generator.check_token(donor, token) is True
    response = api_client.post(
        RESET_CONFIRM_URL,
        {"uid": uid, "token": token, "new_password": GOOD_PASSWORD},
        format="json",
    )
    assert response.status_code == 400
    assert response.json() == {"token": [INVALID_RESET_LINK]}


def test_an_administrator_cannot_send_a_donor_a_reset(
    signed_in: Callable[[User], APIClient], user_admin: User, donor: User
) -> None:
    """The user administrator's send-reset refuses a donor, naming why."""
    response = signed_in(user_admin).post(f"{USERS_URL}/{donor.pk}/send-password-reset")
    assert response.status_code == 400
    assert response.json() == {"detail": "A donor cannot sign in, so no reset email was sent."}


def test_the_refused_reset_for_a_donor_is_audited(
    signed_in: Callable[[User], APIClient],
    user_admin: User,
    donor: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The send-reset refusal is an audit line with the ``donor_account`` reason."""
    signed_in(user_admin).post(f"{USERS_URL}/{donor.pk}/send-password-reset")
    assert audit_messages(audit_log) == [
        f"action={audit.PASSWORD_RESET_ADMIN_SENT} actor={user_admin.pk} target={donor.pk} "
        f"reason={audit.REASON_DONOR_ACCOUNT}"
    ]


def test_an_administrator_cannot_send_a_donor_a_verification_message(
    signed_in: Callable[[User], APIClient], user_admin: User, donor: User
) -> None:
    """The user administrator's send-verification refuses a donor, naming why."""
    response = signed_in(user_admin).post(f"{USERS_URL}/{donor.pk}/send-email-verification")
    assert response.status_code == 400
    assert response.json() == {
        "detail": "A donor cannot sign in, so no verification message was sent."
    }


# --------------------------------------------------------------------------
# The user administrator's list and record
# --------------------------------------------------------------------------
def test_the_user_list_carries_each_accounts_kind(
    signed_in: Callable[[User], APIClient], user_admin: User, donor: User
) -> None:
    """``GET /admin/users`` rows carry ``kind``."""
    rows = signed_in(user_admin).get(USERS_URL, {"search": "giver"}).json()["results"]
    assert [row["kind"] for row in rows] == ["donor"]


@pytest.mark.parametrize(
    ("kind", "emails"),
    [
        ("donor", ["giver@example.test"]),
        ("friend", ["friend@example.test"]),
    ],
)
def test_the_user_list_filters_by_kind(
    signed_in: Callable[[User], APIClient],
    user_admin: User,
    donor: User,
    friend: User,
    kind: str,
    emails: list[str],
) -> None:
    """``?kind=`` narrows the user list to accounts of that stored kind."""
    rows = signed_in(user_admin).get(USERS_URL, {"kind": kind}).json()["results"]
    assert [row["email"] for row in rows] == emails


def test_the_user_list_refuses_an_unknown_kind(
    signed_in: Callable[[User], APIClient], user_admin: User
) -> None:
    """``?kind=`` with anything but the three kinds is a 400 naming the choice."""
    response = signed_in(user_admin).get(USERS_URL, {"kind": "bogus"})
    assert response.status_code == 400
    assert response.json() == {
        "kind": ["Select a valid choice. bogus is not one of the available choices."]
    }


def test_the_user_administrator_cannot_change_a_kind(
    signed_in: Callable[[User], APIClient], user_admin: User, friend: User
) -> None:
    """``kind`` is read-only on ``PATCH /admin/users/{id}``."""
    signed_in(user_admin).patch(f"{USERS_URL}/{friend.pk}", {"kind": "member"}, format="json")
    friend.refresh_from_db()
    assert friend.kind == AccountKind.FRIEND


# --------------------------------------------------------------------------
# The account administrator's member record
# --------------------------------------------------------------------------
def test_the_member_list_carries_the_kind(account_admin_client: APIClient, friend: User) -> None:
    """``GET /admin/members`` rows carry ``kind`` and the friend's ``friend`` state."""
    rows = account_admin_client.get(MEMBERS_URL, {"search": "friend@"}).json()["results"]
    assert [(row["kind"], row["membership"]["status"]) for row in rows] == [("friend", "friend")]


def test_the_member_detail_carries_the_kind(account_admin_client: APIClient, friend: User) -> None:
    """``GET /admin/members/{id}`` carries ``kind``."""
    assert account_admin_client.get(f"{MEMBERS_URL}/{friend.pk}").json()["kind"] == "friend"


def test_an_administrator_creates_a_friend(account_admin_client: APIClient) -> None:
    """``POST /admin/members`` with ``kind: friend`` makes a friend."""
    response = account_admin_client.post(
        MEMBERS_URL, {"email": "new.friend@example.test", "kind": "friend"}, format="json"
    )
    assert response.status_code == 201
    assert User.objects.get(email="new.friend@example.test").kind == AccountKind.FRIEND


def test_an_administrator_cannot_create_a_donor(account_admin_client: APIClient) -> None:
    """``kind: donor`` is not a choice an administrator has."""
    response = account_admin_client.post(
        MEMBERS_URL, {"email": "new.donor@example.test", "kind": "donor"}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"kind": ['"donor" is not a valid choice.']}


def test_an_administrator_turns_a_member_into_a_friend(
    account_admin_client: APIClient, pending_friend: User
) -> None:
    """``PATCH`` with ``kind: friend`` makes a friend at once, clearing a pending date."""
    response = account_admin_client.patch(
        f"{MEMBERS_URL}/{pending_friend.pk}", {"kind": "friend"}, format="json"
    )
    assert response.status_code == 200
    pending_friend.refresh_from_db()
    assert (pending_friend.kind, pending_friend.friend_on) == (AccountKind.FRIEND, None)


def test_an_administrators_change_of_kind_is_audited(
    account_admin_client: APIClient,
    account_admin: User,
    member: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The change is an ``account.kind`` audit line naming the administrator."""
    account_admin_client.patch(f"{MEMBERS_URL}/{member.pk}", {"kind": "friend"}, format="json")
    assert (
        f"action={audit.ACCOUNT_KIND} actor={account_admin.pk} target={member.pk} to=friend"
        in audit_messages(audit_log)
    )


def test_an_administrator_cannot_change_a_donors_kind(
    account_admin_client: APIClient, donor: User
) -> None:
    """A donor becomes a member or a friend only by registering."""
    response = account_admin_client.patch(
        f"{MEMBERS_URL}/{donor.pk}", {"kind": "member"}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {
        "kind": ["A donor becomes a member or a friend only by registering."]
    }


def test_a_friend_granted_a_term_by_hand_becomes_a_member(
    account_admin_client: APIClient, friend: User, annual_plan: MembershipPlan
) -> None:
    """A manual grant is membership, just as a payment is."""
    account_admin_client.post(
        f"{MEMBERS_URL}/{friend.pk}/memberships", {"plan": annual_plan.slug}, format="json"
    )
    friend.refresh_from_db()
    assert friend.kind == AccountKind.MEMBER


def test_a_friend_with_a_live_term_still_reads_as_friend(
    friend: User, annual_plan: MembershipPlan
) -> None:
    """A term written straight to the table does not overrule the kind."""
    MembershipFactory(user=friend, plan=annual_plan)
    assert membership_status(friend)["status"] == MembershipState.FRIEND


def test_saving_a_pending_friend_with_the_same_kind_keeps_the_pending_date(
    account_admin_client: APIClient, pending_friend: User
) -> None:
    """A ``PATCH`` that repeats the stored kind leaves a pending ``friend_on`` alone."""
    friend_on = pending_friend.friend_on
    response = account_admin_client.patch(
        f"{MEMBERS_URL}/{pending_friend.pk}",
        {"kind": "member", "first_name": "Renamed"},
        format="json",
    )
    assert response.status_code == 200
    pending_friend.refresh_from_db()
    assert pending_friend.friend_on == friend_on


def test_a_friend_with_a_live_term_is_never_listed_as_expiring(
    account_admin_client: APIClient, friend: User, annual_plan: MembershipPlan
) -> None:
    """``?expiring_within=`` lists members only: a friend has nothing to expire."""
    grant_membership(friend, annual_plan, days_left=10)
    rows = account_admin_client.get(MEMBERS_URL, {"expiring_within": 30}).json()["results"]
    assert [row["email"] for row in rows] == []


def test_a_friend_with_a_live_term_sorts_with_those_who_have_no_expiry(
    account_admin_client: APIClient,
    friend: User,
    member: User,
    annual_plan: MembershipPlan,
) -> None:
    """``?ordering=expires_on`` puts a friend with a live term after a dated member."""
    grant_membership(friend, annual_plan, days_left=10)
    grant_membership(member, annual_plan, days_left=100)
    rows = account_admin_client.get(
        MEMBERS_URL, {"ordering": "expires_on", "search": "@example.test"}
    ).json()["results"]
    emails = [row["email"] for row in rows]
    assert emails.index(member.email) < emails.index(friend.email)
