"""The audit log: one record per privileged action, ids and counts only.

Every test here watches the ``caldart.audit`` logger.  That logger does not
propagate, so pytest's own root handler never sees it; the ``audit_log``
fixture hangs the capture handler on the audit logger itself and leaves its
configured level alone, which is what makes the level and the no-propagate
setting part of what is under test.
"""

from __future__ import annotations

import ast
import gzip
import logging
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.roles import DART_LEADER, MEMBER, SYSTEM_ADMIN
from apps.members.models import MembershipSource, MembershipStatusChoices
from apps.members.services import activate_term
from apps.reminders.models import REMINDER_OFFSETS, ReminderKind
from apps.reminders.services import send_renewal_reminders
from apps.sysadmin import services as sysadmin_services
from apps.sysadmin.management.commands import db_reset as db_reset_command
from caldart import audit
from tests.factories import AircraftFactory, MembershipFactory, PaymentFactory, UserFactory

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings

    from apps.accounts.models import User as UserModel
    from apps.members.models import MembershipPlan

User = get_user_model()

pytestmark = pytest.mark.django_db

USERS_URL = "/api/v1/admin/users"
MEMBERS_URL = "/api/v1/admin/members"
MEMBERSHIPS_URL = "/api/v1/admin/memberships"
BACKUPS_URL = "/api/v1/system/backups"
REMINDER_RUN_URL = "/api/v1/system/reminders/run"
AIRCRAFT_URL = "/api/v1/aircraft"

#: A member whose address and name would be unmistakable in a log line.
TARGET_EMAIL = "gwen.harkness@example.test"
TARGET_FIRST_NAME = "Gwendolyn"
TARGET_LAST_NAME = "Harkness"


# --------------------------------------------------------------------------
# Capture
# --------------------------------------------------------------------------
@pytest.fixture
def audit_log(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    """Capture the ``caldart.audit`` records a test provokes."""
    logger = logging.getLogger(audit.LOGGER_NAME)
    logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)


def messages(caplog: pytest.LogCaptureFixture, level: int | None = None) -> list[str]:
    """Every audit message captured, optionally only those logged at ``level``."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == audit.LOGGER_NAME and (level is None or record.levelno == level)
    ]


def one_message(caplog: pytest.LogCaptureFixture, level: int | None = None) -> str:
    """The single audit message captured, failing when there is not exactly one."""
    captured = messages(caplog, level)
    assert len(captured) == 1
    return captured[0]


@pytest.fixture
def target_member(db: None) -> UserModel:
    """Return the member every administrative action in this file is aimed at."""
    return UserFactory(
        email=TARGET_EMAIL,
        first_name=TARGET_FIRST_NAME,
        last_name=TARGET_LAST_NAME,
        roles=[MEMBER],
    )


@pytest.fixture
def backup_dir(tmp_path: Path, settings: Settings) -> Path:
    """Return a throwaway ``BACKUP_DIR`` so no test touches the repository's."""
    settings.BACKUP_DIR = tmp_path / "backups"
    return sysadmin_services.backup_dir()


@pytest.fixture
def a_backup(backup_dir: Path) -> Path:
    """One dump on disk, with a name the audit log can carry."""
    path = backup_dir / "caldart-20260601-090000.sql.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(b"-- caldart dump\n")
    return path


@pytest.fixture
def fake_pg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the backup helpers run without a ``pg_dump`` or a server."""
    monkeypatch.setattr(
        sysadmin_services,
        "_pg_command",
        lambda tool: ["sh", "-c", "cat >/dev/null 2>/dev/null; printf '%s\\n' '-- dump'"],
    )


# --------------------------------------------------------------------------
# The record helper
# --------------------------------------------------------------------------
def test_a_record_names_the_action_the_actor_and_the_target(
    audit_log: pytest.LogCaptureFixture,
    member: UserModel,
    target_member: UserModel,
) -> None:
    """Ids, counts, flags and slug lists render as space-separated key=value pairs."""
    audit.record(
        "thing.done", actor=member, target=target_member, count=3, ok=True, fields=["a", "b"]
    )
    assert one_message(audit_log) == (
        f"action=thing.done actor={member.pk} target={target_member.pk} count=3 ok=true fields=a,b"
    )


def test_a_record_without_a_target_writes_a_dash(
    audit_log: pytest.LogCaptureFixture,
    member: UserModel,
) -> None:
    """A record with no ``target`` renders ``target=-``."""
    audit.record("thing.done", actor=member)
    assert one_message(audit_log) == f"action=thing.done actor={member.pk} target=-"


def test_a_record_writes_a_dash_for_an_empty_list(
    audit_log: pytest.LogCaptureFixture,
    member: UserModel,
) -> None:
    """An empty slug list field renders as ``field=-``, not an empty string."""
    audit.record("thing.done", actor=member, removed=[])
    assert one_message(audit_log) == f"action=thing.done actor={member.pk} target=- removed=-"


def test_a_command_is_its_own_actor(
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """``audit.COMMAND_ACTOR`` renders as ``actor=command``."""
    audit.record("thing.done", actor=audit.COMMAND_ACTOR)
    assert one_message(audit_log) == "action=thing.done actor=command target=-"


def test_a_record_takes_an_integer_target(
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """An integer ``target`` renders as its own value, with no lookup."""
    audit.record("thing.done", actor=audit.COMMAND_ACTOR, target=17)
    assert one_message(audit_log) == "action=thing.done actor=command target=17"


def test_a_false_flag_renders_as_false(
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """A ``False`` flag renders as ``field=false``, not as an omitted field."""
    audit.record("thing.done", actor=audit.COMMAND_ACTOR, dry_run=False)
    assert one_message(audit_log) == "action=thing.done actor=command target=- dry_run=false"


@pytest.mark.parametrize(
    "value",
    ["gwen@example.test", "Gwendolyn Harkness", 1.5, {"email": "x"}, ["ok", "not ok"], None],
    ids=["email", "name", "float", "dict", "list-with-a-space", "none"],
)
def test_a_value_that_is_not_an_id_a_count_or_a_slug_is_refused(
    value: object,
) -> None:
    """Nothing but ints, bools, slugs and lists of slugs can reach the log."""
    with pytest.raises(TypeError) as excinfo:
        audit.record("thing.done", actor=audit.COMMAND_ACTOR, detail=value)
    assert str(excinfo.value) == (
        f"Audit field 'detail' takes an int, a bool, a slug or a list of slugs, not {value!r}."
    )


def test_a_slug_longer_than_the_limit_is_refused() -> None:
    """A slug value past ``MAX_SLUG_LENGTH`` raises ``TypeError``."""
    too_long = "x" * (audit.MAX_SLUG_LENGTH + 1)
    with pytest.raises(TypeError) as excinfo:
        audit.record("thing.done", actor=audit.COMMAND_ACTOR, detail=too_long)
    assert str(excinfo.value) == (
        f"Audit field 'detail' takes an int, a bool, a slug or a list of slugs, not {too_long!r}."
    )


def test_an_actor_that_is_neither_a_user_nor_a_command_is_refused() -> None:
    """A string actor other than ``audit.COMMAND_ACTOR`` raises ``TypeError``."""
    with pytest.raises(TypeError) as excinfo:
        audit.record("thing.done", actor="somebody")
    assert str(excinfo.value) == (
        "Audit actor takes a model instance or 'command', not 'somebody'."
    )


def test_a_target_that_is_not_an_id_is_refused() -> None:
    """A ``target`` that is neither a model instance, an int, nor ``None`` is refused."""
    with pytest.raises(TypeError) as excinfo:
        # Deliberately the wrong type, to exercise audit.record's runtime guard.
        audit.record(
            "thing.done",
            actor=audit.COMMAND_ACTOR,
            target="gwen@example.test",  # type: ignore[arg-type]
        )
    assert str(excinfo.value) == (
        "Audit target takes a model instance, an int or None, not 'gwen@example.test'."
    )


def test_a_refusal_is_recorded_at_warning(
    audit_log: pytest.LogCaptureFixture,
    member: UserModel,
) -> None:
    """``audit.refuse`` logs its message at ``WARNING`` with the given reason."""
    audit.refuse("thing.done", actor=member, reason="not_allowed")
    assert one_message(audit_log, logging.WARNING) == (
        f"action=thing.done actor={member.pk} target=- reason=not_allowed"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("caldart-20260601.sql.gz", "caldart-20260601.sql.gz"),
        ("my backup (1).sql.gz", "my_backup__1_.sql.gz"),
        ("../etc/passwd", "etc_passwd"),
        ("", "unnamed"),
        ("///", "unnamed"),
    ],
    ids=["already-a-slug", "spaces-and-brackets", "traversal", "empty", "separators-only"],
)
def test_an_operator_supplied_name_is_reduced_to_a_slug(
    value: str,
    expected: str,
) -> None:
    """``safe_slug`` is how a file or database name an operator typed reaches the log."""
    assert audit.safe_slug(value) == expected


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
def test_the_audit_logger_is_configured_at_info_and_does_not_propagate(
    settings: Settings,
) -> None:
    """Its own level and handler are what ``LOG_LEVEL`` cannot reach."""
    assert settings.LOGGING["loggers"][audit.LOGGER_NAME] == {
        "level": "INFO",
        "handlers": ["console"],
        "propagate": False,
    }


def test_the_audit_logger_keeps_its_own_level_at_runtime() -> None:
    """The audit logger's runtime level is ``INFO``, matching its configuration."""
    assert logging.getLogger(audit.LOGGER_NAME).level == logging.INFO


def test_the_audit_logger_does_not_reach_the_root_handlers() -> None:
    """The audit logger's ``propagate`` flag is ``False`` at runtime."""
    assert logging.getLogger(audit.LOGGER_NAME).propagate is False


def test_a_record_survives_a_root_logger_raised_to_warning(
    audit_log: pytest.LogCaptureFixture,
    member: UserModel,
) -> None:
    """``LOG_LEVEL=WARNING`` quiets the rest of the application, not the audit trail."""
    root = logging.getLogger()
    original = root.level
    root.setLevel(logging.WARNING)
    try:
        audit.record("thing.done", actor=member)
    finally:
        root.setLevel(original)
    assert one_message(audit_log) == f"action=thing.done actor={member.pk} target=-"


def test_the_audit_module_imports_nothing_from_an_app() -> None:
    """It sits under every app, like the other project foundation modules."""
    path = Path(audit.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = [
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
        for name in [node.module]
    ]
    assert [name for name in imported if name == "apps" or name.startswith("apps.")] == []


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------
def test_an_account_edit_records_the_field_names_only(
    api_client: APIClient,
    user_admin: UserModel,
    target_member: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Changing a name records the changed field name, not its value."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        f"{USERS_URL}/{target_member.pk}", {"first_name": "Renamed"}, format="json"
    )
    assert response.status_code == 200
    assert one_message(audit_log) == (
        f"action=account.update actor={user_admin.pk} target={target_member.pk} fields=first_name"
    )


def test_an_email_change_records_the_field_name_and_not_the_address(
    api_client: APIClient,
    user_admin: UserModel,
    target_member: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Changing the email address records the field name ``email``, not its value."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        f"{USERS_URL}/{target_member.pk}", {"email": "moved@example.test"}, format="json"
    )
    assert response.status_code == 200
    assert one_message(audit_log) == (
        f"action=account.update actor={user_admin.pk} target={target_member.pk} fields=email"
    )


def test_a_role_change_records_the_slugs_added_and_removed(
    api_client: APIClient,
    user_admin: UserModel,
    target_member: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """A role change records the slugs added and the slugs removed, each as a list."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        f"{USERS_URL}/{target_member.pk}", {"roles": [DART_LEADER]}, format="json"
    )
    assert response.status_code == 200
    assert one_message(audit_log) == (
        f"action=account.roles actor={user_admin.pk} target={target_member.pk} "
        f"added=dart_leader removed=member"
    )


def test_a_deactivation_is_its_own_action(
    api_client: APIClient,
    user_admin: UserModel,
    target_member: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Setting ``is_active`` to ``False`` logs ``account.deactivate``, not an update."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        f"{USERS_URL}/{target_member.pk}", {"is_active": False}, format="json"
    )
    assert response.status_code == 200
    assert one_message(audit_log) == (
        f"action=account.deactivate actor={user_admin.pk} target={target_member.pk}"
    )


def test_an_activation_is_its_own_action(
    api_client: APIClient,
    user_admin: UserModel,
    target_member: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Setting ``is_active`` to ``True`` logs ``account.activate``, not a plain update."""
    target_member.is_active = False
    target_member.save(update_fields=["is_active"])
    api_client.force_login(user_admin)
    response = api_client.patch(
        f"{USERS_URL}/{target_member.pk}", {"is_active": True}, format="json"
    )
    assert response.status_code == 200
    assert one_message(audit_log) == (
        f"action=account.activate actor={user_admin.pk} target={target_member.pk}"
    )


def test_an_edit_that_changes_nothing_records_nothing(
    api_client: APIClient,
    user_admin: UserModel,
    target_member: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Resending the stored values is not a change, so it is not an entry."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        f"{USERS_URL}/{target_member.pk}",
        {
            "email": TARGET_EMAIL,
            "first_name": TARGET_FIRST_NAME,
            "last_name": TARGET_LAST_NAME,
            "is_active": True,
        },
        format="json",
    )
    assert response.status_code == 200
    assert messages(audit_log) == []


def test_an_edit_records_only_the_columns_whose_value_changes(
    api_client: APIClient,
    user_admin: UserModel,
    target_member: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The portal resends the whole form, so an unaltered column is not a field name."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        f"{USERS_URL}/{target_member.pk}",
        {
            "email": TARGET_EMAIL,
            "first_name": "Renamed",
            "last_name": TARGET_LAST_NAME,
            "is_active": True,
        },
        format="json",
    )
    assert response.status_code == 200
    assert one_message(audit_log) == (
        f"action=account.update actor={user_admin.pk} target={target_member.pk} fields=first_name"
    )


def test_a_self_deactivation_is_refused_and_recorded(
    api_client: APIClient,
    user_admin: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """An administrator deactivating their own account is refused and logged."""
    api_client.force_login(user_admin)
    response = api_client.patch(f"{USERS_URL}/{user_admin.pk}", {"is_active": False}, format="json")
    assert response.status_code == 400
    assert one_message(audit_log, logging.WARNING) == (
        f"action=account.deactivate actor={user_admin.pk} target={user_admin.pk} "
        f"fields=is_active reason=self_deactivation"
    )


def test_an_email_change_on_a_higher_account_is_refused_and_recorded(
    api_client: APIClient,
    user_admin: UserModel,
    system_admin: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """A user administrator editing a system administrator is refused and logged."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        f"{USERS_URL}/{system_admin.pk}", {"email": "taken-over@example.test"}, format="json"
    )
    assert response.status_code == 400
    assert one_message(audit_log, logging.WARNING) == (
        f"action=account.update actor={user_admin.pk} target={system_admin.pk} "
        f"fields=email reason=roles_not_held"
    )


def test_a_system_admin_role_grant_is_refused_and_recorded(
    api_client: APIClient,
    user_admin: UserModel,
    target_member: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Granting the system-admin role is refused and logged at warning."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        f"{USERS_URL}/{target_member.pk}", {"roles": [MEMBER, SYSTEM_ADMIN]}, format="json"
    )
    assert response.status_code == 400
    assert one_message(audit_log, logging.WARNING) == (
        f"action=account.roles actor={user_admin.pk} target={target_member.pk} "
        f"reason=system_admin_role"
    )


def test_an_admin_password_reset_records_the_target(
    api_client: APIClient,
    user_admin: UserModel,
    target_member: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Sending an administrator password reset logs the target account."""
    api_client.force_login(user_admin)
    response = api_client.post(f"{USERS_URL}/{target_member.pk}/send-password-reset")
    assert response.status_code == 200
    assert one_message(audit_log) == (
        f"action=password_reset.admin_sent actor={user_admin.pk} target={target_member.pk}"
    )


def test_a_reset_for_a_deactivated_account_is_refused_and_recorded(
    api_client: APIClient,
    user_admin: UserModel,
    target_member: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """A password reset for a deactivated account is refused and logged at warning."""
    target_member.is_active = False
    target_member.save(update_fields=["is_active"])
    api_client.force_login(user_admin)
    response = api_client.post(f"{USERS_URL}/{target_member.pk}/send-password-reset")
    assert response.status_code == 400
    assert one_message(audit_log, logging.WARNING) == (
        f"action=password_reset.admin_sent actor={user_admin.pk} target={target_member.pk} "
        f"reason=inactive_account"
    )


# --------------------------------------------------------------------------
# Members and memberships
# --------------------------------------------------------------------------
def test_creating_a_member_records_the_account_and_the_invitation(
    api_client: APIClient,
    account_admin: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Creating a member records the new account's id and that it was invited."""
    api_client.force_login(account_admin)
    response = api_client.post(MEMBERS_URL, {"email": "invited@example.test"}, format="json")
    assert response.status_code == 201
    assert one_message(audit_log) == (
        f"action=member.create actor={account_admin.pk} target={response.json()['id']} invited=true"
    )


def test_deleting_a_member_records_the_account(
    api_client: APIClient,
    account_admin: UserModel,
    target_member: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Deleting a member records the deleted account's id."""
    api_client.force_login(account_admin)
    response = api_client.delete(f"{MEMBERS_URL}/{target_member.pk}")
    assert response.status_code == 204
    assert one_message(audit_log) == (
        f"action=member.delete actor={account_admin.pk} target={target_member.pk}"
    )


def test_deleting_your_own_account_is_refused_and_recorded(
    api_client: APIClient,
    account_admin: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """An account administrator deleting their own account is refused and logged."""
    api_client.force_login(account_admin)
    response = api_client.delete(f"{MEMBERS_URL}/{account_admin.pk}")
    assert response.status_code == 403
    assert one_message(audit_log, logging.WARNING) == (
        f"action=member.delete actor={account_admin.pk} target={account_admin.pk} "
        f"reason=self_delete"
    )


def test_deleting_a_system_admin_is_refused_and_recorded(
    api_client: APIClient,
    account_admin: UserModel,
    system_admin: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Deleting a system administrator's account is refused and logged at warning."""
    api_client.force_login(account_admin)
    response = api_client.delete(f"{MEMBERS_URL}/{system_admin.pk}")
    assert response.status_code == 403
    assert one_message(audit_log, logging.WARNING) == (
        f"action=member.delete actor={account_admin.pk} target={system_admin.pk} "
        f"reason=system_admin_target"
    )


def test_deleting_a_member_with_a_payment_is_refused_and_recorded(
    api_client: APIClient,
    account_admin: UserModel,
    target_member: UserModel,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Deleting a member who has a payment is refused and logged at warning."""
    PaymentFactory(user=target_member, plan=annual_plan)
    api_client.force_login(account_admin)
    response = api_client.delete(f"{MEMBERS_URL}/{target_member.pk}")
    assert response.status_code == 403
    assert one_message(audit_log, logging.WARNING) == (
        f"action=member.delete actor={account_admin.pk} target={target_member.pk} "
        f"reason=has_payments"
    )


def test_granting_a_term_records_the_plan_and_the_term(
    api_client: APIClient,
    account_admin: UserModel,
    target_member: UserModel,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Granting a membership term records the plan slug and the new term's id."""
    api_client.force_login(account_admin)
    response = api_client.post(
        f"{MEMBERS_URL}/{target_member.pk}/memberships", {"plan": annual_plan.slug}, format="json"
    )
    assert response.status_code == 201
    assert one_message(audit_log) == (
        f"action=membership.grant actor={account_admin.pk} target={target_member.pk} "
        f"plan={annual_plan.slug} term={response.json()['id']}"
    )


def test_correcting_a_term_records_the_changed_field_names(
    api_client: APIClient,
    account_admin: UserModel,
    target_member: UserModel,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Correcting a granted term records the term's id and the changed field names."""
    term = activate_term(target_member, annual_plan, source=MembershipSource.MANUAL)
    assert term.ends_on is not None
    api_client.force_login(account_admin)
    response = api_client.patch(
        f"{MEMBERSHIPS_URL}/{term.pk}",
        {"ends_on": (term.ends_on + timedelta(days=30)).isoformat()},
        format="json",
    )
    assert response.status_code == 200
    assert one_message(audit_log) == (
        f"action=membership.correct actor={account_admin.pk} target={target_member.pk} "
        f"term={term.pk} fields=ends_on"
    )


def test_a_correction_that_changes_nothing_records_no_field(
    api_client: APIClient,
    account_admin: UserModel,
    target_member: UserModel,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """A correction that resends the stored status records no changed field."""
    term = activate_term(target_member, annual_plan, source=MembershipSource.MANUAL)
    api_client.force_login(account_admin)
    response = api_client.patch(
        f"{MEMBERSHIPS_URL}/{term.pk}",
        {"status": MembershipStatusChoices.ACTIVE},
        format="json",
    )
    assert response.status_code == 200
    assert one_message(audit_log) == (
        f"action=membership.correct actor={account_admin.pk} target={target_member.pk} "
        f"term={term.pk} fields=-"
    )


# --------------------------------------------------------------------------
# The aircraft register
# --------------------------------------------------------------------------
def test_adding_an_aircraft_records_the_record(
    api_client: APIClient,
    member: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Adding an airframe records the id of the record it created."""
    api_client.force_login(member)
    response = api_client.post(
        AIRCRAFT_URL, {"n_number": "N4321Q", "make": "Cirrus", "model": "SR22"}, format="json"
    )
    assert response.status_code == 201
    assert one_message(audit_log) == (
        f"action=aircraft.create actor={member.pk} target={response.json()['id']}"
    )


def test_editing_an_aircraft_records_the_columns_that_changed(
    api_client: APIClient,
    account_admin: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The register's form resends every field, so only what moved is a field name."""
    aircraft = AircraftFactory(n_number="N77AU", make="Cessna", model="182T Skylane")
    api_client.force_login(account_admin)
    response = api_client.patch(
        f"{AIRCRAFT_URL}/{aircraft.pk}", {"make": "Cessna", "model": "SR22"}, format="json"
    )
    assert response.status_code == 200
    assert one_message(audit_log) == (
        f"action=aircraft.update actor={account_admin.pk} target={aircraft.pk} fields=model"
    )


def test_an_edit_that_moves_no_aircraft_column_records_a_dash(
    api_client: APIClient,
    account_admin: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """A save that alters nothing is still a write, with no column named."""
    aircraft = AircraftFactory(n_number="N78AU", make="Cessna", model="182T Skylane")
    api_client.force_login(account_admin)
    response = api_client.patch(f"{AIRCRAFT_URL}/{aircraft.pk}", {"make": "Cessna"}, format="json")
    assert response.status_code == 200
    assert one_message(audit_log) == (
        f"action=aircraft.update actor={account_admin.pk} target={aircraft.pk} fields=-"
    )


def test_deleting_an_aircraft_records_the_record(
    api_client: APIClient,
    account_admin: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Deleting an airframe records the id of the record that is gone."""
    aircraft = AircraftFactory(n_number="N79AU")
    api_client.force_login(account_admin)
    response = api_client.delete(f"{AIRCRAFT_URL}/{aircraft.pk}")
    assert response.status_code == 204
    assert one_message(audit_log) == (
        f"action=aircraft.delete actor={account_admin.pk} target={aircraft.pk}"
    )


# --------------------------------------------------------------------------
# Backups, the database and the reminder scan
# --------------------------------------------------------------------------
def test_creating_a_backup_records_the_file_and_its_size(
    api_client: APIClient,
    system_admin: UserModel,
    backup_dir: Path,
    fake_pg: None,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Creating a backup records its file name and its size in bytes."""
    api_client.force_login(system_admin)
    response = api_client.post(BACKUPS_URL)
    assert response.status_code == 201
    body = response.json()
    assert one_message(audit_log) == (
        f"action=backup.create actor={system_admin.pk} target=- "
        f"file={body['name']} size={body['size_bytes']}"
    )


def test_downloading_a_backup_records_the_file(
    api_client: APIClient,
    system_admin: UserModel,
    a_backup: Path,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Downloading a backup records its file name."""
    api_client.force_login(system_admin)
    response = api_client.get(f"{BACKUPS_URL}/{a_backup.name}/download")
    assert response.status_code == 200
    response.close()
    assert one_message(audit_log) == (
        f"action=backup.download actor={system_admin.pk} target=- file={a_backup.name}"
    )


def test_downloading_a_backup_that_is_not_there_is_refused_and_recorded(
    api_client: APIClient,
    system_admin: UserModel,
    backup_dir: Path,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The refused name is attacker-controlled, so only the refusal is recorded."""
    api_client.force_login(system_admin)
    response = api_client.get(f"{BACKUPS_URL}/../../etc/passwd/download")
    assert response.status_code == 404
    assert one_message(audit_log, logging.WARNING) == (
        f"action=backup.download actor={system_admin.pk} target=- reason=no_such_backup"
    )


def test_restoring_a_backup_records_the_file_against_the_command(
    a_backup: Path,
    fake_pg: None,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Restoring a backup on the command line records its file name."""
    sysadmin_services.restore_backup(a_backup, drop_first=False)
    assert one_message(audit_log) == (
        f"action=backup.restore actor=command target=- file={a_backup.name}"
    )


def test_resetting_the_database_records_it_against_the_command(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The drop and the re-migrate are stubbed; the command's own path is not."""
    monkeypatch.setattr(db_reset_command, "drop_schema", lambda: None)
    monkeypatch.setattr(db_reset_command, "call_command", lambda *args, **kwargs: None)
    call_command("db_reset", "--noinput")
    assert one_message(audit_log) == (
        f"action=db.reset actor=command target=- "
        f"database={settings.DATABASES['default']['NAME']} seeded=false"
    )


def test_a_reminder_run_from_the_command_line_records_its_counts(
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """A reminder run from the command line records its sent/skipped/failed counts."""
    send_renewal_reminders()
    assert one_message(audit_log) == (
        "action=reminders.run actor=command target=- "
        "dry_run=false sent=0 skipped=0 failed=0 expired_flipped=0"
    )


def test_a_reminder_run_from_the_panel_records_the_administrator(
    api_client: APIClient,
    system_admin: UserModel,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """A reminder run started from the admin panel records the administrator as actor."""
    api_client.force_login(system_admin)
    response = api_client.post(REMINDER_RUN_URL, {"dry_run": True}, format="json")
    assert response.status_code == 200
    assert one_message(audit_log) == (
        f"action=reminders.run actor={system_admin.pk} target=- "
        f"dry_run=true sent=0 skipped=0 failed=0 expired_flipped=0"
    )


def test_a_reminder_run_counts_what_it_sent(
    api_client: APIClient,
    system_admin: UserModel,
    target_member: UserModel,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
    today: date,
) -> None:
    """One member sixty days from expiry is one email, and one line saying so."""
    MembershipFactory(
        user=target_member,
        plan=annual_plan,
        starts_on=today - timedelta(days=305),
        ends_on=today - timedelta(days=REMINDER_OFFSETS[ReminderKind.T60]),
    )
    api_client.force_login(system_admin)
    response = api_client.post(REMINDER_RUN_URL, {"dry_run": False}, format="json")
    assert response.status_code == 200
    assert one_message(audit_log) == (
        f"action=reminders.run actor={system_admin.pk} target=- "
        f"dry_run=false sent=1 skipped=0 failed=0 expired_flipped=0"
    )


# --------------------------------------------------------------------------
# No personal data, whatever the action
# --------------------------------------------------------------------------
def test_no_record_carries_an_email_address_or_a_name(
    api_client: APIClient,
    user_admin: UserModel,
    account_admin: UserModel,
    target_member: UserModel,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The whole point of the field rules: a log line is ids, counts and slugs."""
    api_client.force_login(user_admin)
    api_client.patch(
        f"{USERS_URL}/{target_member.pk}",
        {"first_name": "Renamed", "roles": [DART_LEADER]},
        format="json",
    )
    api_client.post(f"{USERS_URL}/{target_member.pk}/send-password-reset")

    api_client.force_login(account_admin)
    api_client.post(MEMBERS_URL, {"email": TARGET_EMAIL.upper()}, format="json")
    api_client.post(
        f"{MEMBERS_URL}/{target_member.pk}/memberships", {"plan": annual_plan.slug}, format="json"
    )
    api_client.delete(f"{MEMBERS_URL}/{target_member.pk}")

    personal = ["@", TARGET_FIRST_NAME, TARGET_LAST_NAME, "Renamed"]
    assert [
        message for message in messages(audit_log) if any(needle in message for needle in personal)
    ] == []
