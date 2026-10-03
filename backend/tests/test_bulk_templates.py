"""Saved bulk email templates: saving, listing, changing, deleting, and using one.

A template is a message saved under a name and shared by CalDART management.  **Start
from a template** fills a draft with its subject, message, and type; the draft is a
copy, so changing it leaves the template as it was.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient

from apps.accounts.roles import MANAGEMENT, SYSTEM_ADMIN
from apps.bulk_email.models import BulkEmail, BulkEmailStatus, EmailTemplate
from tests.conftest import role_matrix
from tests.factories import (
    BulkEmailFactory,
    EmailTemplateFactory,
    EmailTypeFactory,
    add_to_batch,
    make_person,
    operational_type,
)

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

TEMPLATES_URL = "/api/v1/bulk-email/templates"


def template_url(template: EmailTemplate) -> str:
    """``/api/v1/bulk-email/templates/{id}`` for ``template``."""
    return f"{TEMPLATES_URL}/{template.pk}"


def apply_url(bulk: BulkEmail) -> str:
    """``/api/v1/bulk-email/{id}/apply-template`` for ``bulk``."""
    return f"/api/v1/bulk-email/{bulk.pk}/apply-template"


@pytest.fixture
def newsletter() -> EmailTemplate:
    """The monthly newsletter template, Operational, with a Reply-To of its own."""
    return EmailTemplateFactory(
        name="Monthly newsletter",
        subject="News for {first_name}",
        body="<p>Dear {first_name|friend},</p><p>The hangar is open.</p>",
        email_type=operational_type(),
        reply_to="news@example.test",
    )


@pytest.fixture
def draft(management: User) -> BulkEmail:
    """An empty draft from CalDART management, with no type."""
    return BulkEmailFactory(sender=management, subject="", body="", email_type=None)


# --------------------------------------------------------------------------
# Saving and listing
# --------------------------------------------------------------------------
def test_saving_a_template_answers_it_with_its_author(
    management_client: APIClient, management: User
) -> None:
    """``POST`` saves the message under its name, the caller as its author."""
    response = management_client.post(
        TEMPLATES_URL,
        {
            "name": "Meeting notice",
            "subject": "Meeting on Saturday",
            "body": "<p>See you there.</p>",
            "email_type": operational_type().pk,
            "reply_to": "board@example.test",
        },
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert {key: body[key] for key in ("name", "subject", "body", "email_type_name")} == {
        "name": "Meeting notice",
        "subject": "Meeting on Saturday",
        "body": "<p>See you there.</p>",
        "email_type_name": "Operational",
    }
    assert body["created_by"] == management.display_name


def test_a_saved_template_keeps_its_reply_to(management_client: APIClient) -> None:
    """The Reply-To address is saved with the template."""
    management_client.post(
        TEMPLATES_URL,
        {"name": "Notice", "reply_to": "board@example.test"},
        format="json",
    )
    assert EmailTemplate.objects.get(name="Notice").reply_to == "board@example.test"


def test_a_template_message_is_saved_sanitized(management_client: APIClient) -> None:
    """A script in the message is gone once it is saved, as from a draft."""
    management_client.post(
        TEMPLATES_URL,
        {"name": "Notice", "body": "<p>Hi</p><script>alert(1)</script>"},
        format="json",
    )
    assert EmailTemplate.objects.get(name="Notice").body == "<p>Hi</p>"


def test_the_list_holds_every_template_by_name(management_client: APIClient) -> None:
    """Templates are listed by name, ignoring case, and shared by every manager."""
    EmailTemplateFactory(name="b notice")
    EmailTemplateFactory(name="A newsletter")
    EmailTemplateFactory(name="Callout")
    names = [row["name"] for row in management_client.get(TEMPLATES_URL).json()]
    assert names == ["A newsletter", "b notice", "Callout"]


@pytest.mark.parametrize(
    "name", ["Monthly newsletter", "monthly NEWSLETTER"], ids=["same", "other-case"]
)
def test_a_template_name_is_unique_ignoring_case(
    management_client: APIClient, newsletter: EmailTemplate, name: str
) -> None:
    """A second template cannot take a name another has."""
    response = management_client.post(TEMPLATES_URL, {"name": name}, format="json")
    assert response.status_code == 400
    assert response.json() == {
        "name": [f'A template named "{name}" already exists. Choose another name.']
    }


def test_a_template_needs_a_name(management_client: APIClient) -> None:
    """A blank name is refused."""
    response = management_client.post(TEMPLATES_URL, {"name": " "}, format="json")
    assert response.status_code == 400
    assert response.json() == {"name": ["This field may not be blank."]}


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("subject", "Two\nlines", "A subject is one line."),
        ("reply_to", "not an address", "Enter a valid email address."),
    ],
    ids=["subject", "reply_to"],
)
def test_a_template_field_a_draft_would_refuse_is_refused(
    management_client: APIClient, field: str, value: str, message: str
) -> None:
    """A template's fields follow a draft's rules."""
    response = management_client.post(
        TEMPLATES_URL, {"name": "Notice", field: value}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {field: [message]}


def test_a_template_message_with_an_unknown_field_is_refused(
    management_client: APIClient,
) -> None:
    """A token that is not a recipient field is refused, as in a draft."""
    response = management_client.post(
        TEMPLATES_URL, {"name": "Notice", "body": "<p>Hi {nickname}</p>"}, format="json"
    )
    assert response.status_code == 400
    assert response.json()["body"][0].startswith("{nickname} is not a recipient field.")


def test_a_template_type_the_caller_may_not_send_is_refused(
    management_client: APIClient,
) -> None:
    """The type must be one the caller may send."""
    board = EmailTypeFactory(name="Board", sender_roles=[])
    response = management_client.post(
        TEMPLATES_URL, {"name": "Notice", "email_type": board.pk}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"email_type": ["You cannot send Board email. Choose another type."]}


# --------------------------------------------------------------------------
# Renaming, editing, and deleting
# --------------------------------------------------------------------------
def test_renaming_a_template_keeps_its_message(
    management_client: APIClient, newsletter: EmailTemplate
) -> None:
    """``PATCH`` with a name renames the template and leaves the rest."""
    response = management_client.patch(
        template_url(newsletter), {"name": "Spring newsletter"}, format="json"
    )
    assert response.status_code == 200
    newsletter.refresh_from_db()
    assert (newsletter.name, newsletter.subject) == ("Spring newsletter", "News for {first_name}")


def test_a_template_may_keep_its_own_name_in_another_case(
    management_client: APIClient, newsletter: EmailTemplate
) -> None:
    """Renaming to the same words in another case is not a clash with itself."""
    response = management_client.patch(
        template_url(newsletter), {"name": "MONTHLY newsletter"}, format="json"
    )
    assert response.status_code == 200


def test_renaming_to_another_template_name_is_refused(
    management_client: APIClient, newsletter: EmailTemplate
) -> None:
    """A rename cannot take another template's name."""
    other = EmailTemplateFactory(name="Callout")
    response = management_client.patch(
        template_url(other), {"name": "Monthly newsletter"}, format="json"
    )
    assert response.status_code == 400


def test_editing_a_template_changes_its_message(
    management_client: APIClient, newsletter: EmailTemplate
) -> None:
    """``PATCH`` saves the subject and message given."""
    management_client.patch(
        template_url(newsletter),
        {"subject": "April news", "body": "<p>Fly-in on the 12th.</p>"},
        format="json",
    )
    newsletter.refresh_from_db()
    assert (newsletter.subject, newsletter.body) == ("April news", "<p>Fly-in on the 12th.</p>")


def test_a_template_type_can_be_cleared(
    management_client: APIClient, newsletter: EmailTemplate
) -> None:
    """A null type leaves the template with none."""
    management_client.patch(template_url(newsletter), {"email_type": None}, format="json")
    newsletter.refresh_from_db()
    assert newsletter.email_type is None


def test_deleting_a_template_removes_it(
    management_client: APIClient, newsletter: EmailTemplate
) -> None:
    """``DELETE`` answers 204 and the template is gone."""
    response = management_client.delete(template_url(newsletter))
    assert response.status_code == 204
    assert not EmailTemplate.objects.filter(pk=newsletter.pk).exists()


def test_deleting_a_template_leaves_drafts_started_from_it(
    management_client: APIClient, newsletter: EmailTemplate, draft: BulkEmail
) -> None:
    """A draft filled from a template keeps its words once the template is deleted."""
    management_client.post(apply_url(draft), {"template": newsletter.pk}, format="json")
    management_client.delete(template_url(newsletter))
    draft.refresh_from_db()
    assert draft.subject == "News for {first_name}"


def test_deleting_its_type_leaves_the_template_without_one(newsletter: EmailTemplate) -> None:
    """A template's type is cleared, not protected, when the type is deleted."""
    newsletter.email_type = EmailTypeFactory(name="Board")
    newsletter.save()
    newsletter.email_type.delete()
    newsletter.refresh_from_db()
    assert newsletter.email_type is None


# --------------------------------------------------------------------------
# Starting a draft from a template
# --------------------------------------------------------------------------
def test_starting_from_a_template_fills_the_draft(
    management_client: APIClient, newsletter: EmailTemplate, draft: BulkEmail
) -> None:
    """The draft takes the template's subject, message, and type."""
    response = management_client.post(apply_url(draft), {"template": newsletter.pk}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert (body["subject"], body["body"], body["email_type_name"]) == (
        "News for {first_name}",
        "<p>Dear {first_name|friend},</p><p>The hangar is open.</p>",
        "Operational",
    )


def test_starting_from_a_template_leaves_the_batch(
    management_client: APIClient, newsletter: EmailTemplate, draft: BulkEmail
) -> None:
    """A template holds content, not people: the batch is not touched."""
    add_to_batch(draft, make_person("ann@example.test"))
    management_client.post(apply_url(draft), {"template": newsletter.pk}, format="json")
    assert draft.recipients.count() == 1


def test_a_template_without_a_type_keeps_the_drafts_type(
    management_client: APIClient, management: User
) -> None:
    """The draft keeps its own type when the template names none."""
    bulk = BulkEmailFactory(sender=management)
    template = EmailTemplateFactory(email_type=None)
    management_client.post(apply_url(bulk), {"template": template.pk}, format="json")
    bulk.refresh_from_db()
    assert bulk.email_type == operational_type()


def test_a_template_type_the_caller_may_not_send_is_not_applied(
    management_client: APIClient, draft: BulkEmail
) -> None:
    """A type the caller may not send is left out; the words still fill in."""
    template = EmailTemplateFactory(email_type=EmailTypeFactory(name="Board", sender_roles=[]))
    management_client.post(apply_url(draft), {"template": template.pk}, format="json")
    draft.refresh_from_db()
    assert draft.email_type is None


def test_editing_the_draft_leaves_the_template_unchanged(
    management_client: APIClient, newsletter: EmailTemplate, draft: BulkEmail
) -> None:
    """The draft is a copy: saving new words in it changes no template."""
    management_client.post(apply_url(draft), {"template": newsletter.pk}, format="json")
    management_client.patch(
        f"/api/v1/bulk-email/{draft.pk}",
        {"subject": "Changed", "body": "<p>New</p>"},
        format="json",
    )
    newsletter.refresh_from_db()
    assert (newsletter.subject, newsletter.body) == (
        "News for {first_name}",
        "<p>Dear {first_name|friend},</p><p>The hangar is open.</p>",
    )


def test_an_unknown_template_is_refused(management_client: APIClient, draft: BulkEmail) -> None:
    """A template id nobody has is a 400 keyed ``template``."""
    response = management_client.post(apply_url(draft), {"template": 9999}, format="json")
    assert response.status_code == 400
    assert list(response.json()) == ["template"]


def test_a_template_cannot_fill_an_email_that_has_started(
    management_client: APIClient, management: User, newsletter: EmailTemplate
) -> None:
    """Once an email has started sending it is a 409, and it keeps its words."""
    started = BulkEmailFactory(
        sender=management, status=BulkEmailStatus.SENT, started_at="2026-01-01T00:00Z"
    )
    response = management_client.post(
        apply_url(started), {"template": newsletter.pk}, format="json"
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "This email has been sent and cannot be changed."}


def test_a_blank_template_cannot_empty_a_queued_email(
    management_client: APIClient, management: User
) -> None:
    """A queued email cannot be left without a subject, as a save refuses it."""
    queued = BulkEmailFactory(sender=management, status=BulkEmailStatus.QUEUED)
    blank = EmailTemplateFactory(subject="", body="")
    response = management_client.post(apply_url(queued), {"template": blank.pk}, format="json")
    assert response.status_code == 400
    assert response.json() == {"subject": ["Write a subject."]}


# --------------------------------------------------------------------------
# Who may
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
@pytest.mark.parametrize(
    ("method", "path", "payload", "code"),
    [
        ("get", "", None, 200),
        ("post", "", {"name": "Fresh"}, 201),
        ("get", "/{id}", None, 200),
        ("patch", "/{id}", {"name": "Renamed"}, 200),
        ("delete", "/{id}", None, 204),
    ],
    ids=["list", "create", "read", "update", "delete"],
)
def test_only_management_reaches_the_templates(
    api_client: APIClient,
    all_role_users: dict[str, User],
    newsletter: EmailTemplate,
    role: str,
    allowed: bool,
    method: str,
    path: str,
    payload: dict[str, str] | None,
    code: int,
) -> None:
    """Templates are CalDART management's and the system administrator's alone."""
    api_client.force_login(all_role_users[role])
    response = getattr(api_client, method)(
        f"{TEMPLATES_URL}{path.format(id=newsletter.pk)}", payload, format="json"
    )
    assert response.status_code == (code if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
def test_only_management_starts_a_draft_from_a_template(
    api_client: APIClient,
    all_role_users: dict[str, User],
    newsletter: EmailTemplate,
    draft: BulkEmail,
    role: str,
    allowed: bool,
) -> None:
    """**Start from a template** is management's and the system administrator's."""
    api_client.force_login(all_role_users[role])
    response = api_client.post(apply_url(draft), {"template": newsletter.pk}, format="json")
    assert response.status_code == (200 if allowed else 403)


def test_an_anonymous_caller_is_refused_the_templates(api_client: APIClient) -> None:
    """Signing in comes first."""
    assert api_client.get(TEMPLATES_URL).status_code == 401
