"""Two clicks on one donor's verification link at the same moment.

Both requests read the account before either writes it, so nothing but a lock stops
both from upgrading it.  ``verify_email`` re-reads the account with
``select_for_update``, so the second caller waits at the row until the first has
committed and then finds a donor who is already a member: it verifies the address
again harmlessly but does not run the upgrade a second time.  These tests run that
collision for real, in two threads against the live database.
"""

from __future__ import annotations

import threading
import time

import pytest
from django.db import connections

from apps.accounts import services as account_services
from apps.accounts.models import AccountKind, User
from apps.accounts.services import DonorUpgrade, make_email_verification_token, verify_email
from caldart import audit
from tests.conftest import audit_messages
from tests.factories import UserFactory

# The threads must see each other's committed rows, so this module runs against
# a real, committing database rather than the usual wrapping transaction.
pytestmark = pytest.mark.django_db(transaction=True)

#: How long the first verification holds the account inside its transaction.
#: Long enough that the second caller reaches the row while the first still
#: holds it, so a read taken without the lock really would see a donor.
HOLD_SECONDS = 0.3

#: How long a thread waits for its partner at the barrier, and the test for the
#: threads, before giving up rather than hanging the suite.
JOIN_TIMEOUT_SECONDS = 30.0


@pytest.fixture
def held_upgrade(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Record each donor upgrade, holding the caller in its transaction while it runs.

    The returned list grows by the donor's id every time ``verify_email`` gets as
    far as upgrading the account, which is the step the second caller must not
    reach.  The hold widens the window the lock has to close.
    """
    calls: list[int] = []

    def held_upgrade_donor(donor: User, upgrade: DonorUpgrade) -> None:
        calls.append(donor.pk)
        time.sleep(HOLD_SECONDS)
        real_upgrade_donor(donor, upgrade)

    real_upgrade_donor = account_services.upgrade_donor
    monkeypatch.setattr(account_services, "upgrade_donor", held_upgrade_donor)
    return calls


def verify_in_thread(token: str, start: threading.Barrier, failures: list[str]) -> None:
    """Follow ``token`` as soon as the other thread is ready, recording any error."""
    try:
        start.wait(timeout=JOIN_TIMEOUT_SECONDS)
        verify_email(token)
    # A thread's exception would otherwise be printed and lost; the test asserts
    # on what it caught instead.
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")
    finally:
        # Each thread opened its own connection; leaving it open would keep the
        # test database busy and stall the teardown that flushes the tables.
        connections.close_all()


def verify_twice_at_once(token: str) -> list[str]:
    """Follow ``token`` in two threads in parallel, returning what they raised."""
    start = threading.Barrier(2)
    failures: list[str] = []
    threads = [
        threading.Thread(target=verify_in_thread, args=(token, start, failures)) for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=JOIN_TIMEOUT_SECONDS)
    assert [thread.is_alive() for thread in threads] == [False, False]
    return failures


@pytest.fixture
def donor_token() -> tuple[User, str]:
    """A donor and the verification link that upgrades them to a member."""
    donor = UserFactory(email="giver@example.test", kind=AccountKind.DONOR, roles=[])
    token = make_email_verification_token(
        donor, upgrade={"first_name": "Gil", "last_name": "Ives", "kind": "member"}
    )
    return donor, token


def test_the_second_click_does_not_reach_the_upgrade(
    donor_token: tuple[User, str], held_upgrade: list[int]
) -> None:
    """Only the caller that wins the row upgrades the donor; the other returns early."""
    donor, token = donor_token

    failures = verify_twice_at_once(token)

    assert failures == []
    assert held_upgrade == [donor.pk]


def test_two_simultaneous_clicks_leave_the_donor_a_member_once(
    donor_token: tuple[User, str], held_upgrade: list[int]
) -> None:
    """The collision ends with the donor a member, not upgraded a second time."""
    donor, token = donor_token

    verify_twice_at_once(token)

    donor.refresh_from_db()
    assert donor.kind == AccountKind.MEMBER


def test_two_simultaneous_clicks_write_one_account_kind_record(
    donor_token: tuple[User, str],
    held_upgrade: list[int],
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The lock leaves exactly one ``account.kind`` audit record, not two."""
    _, token = donor_token

    verify_twice_at_once(token)

    action = f"action={audit.ACCOUNT_KIND}"
    kind_records = [msg for msg in audit_messages(audit_log) if action in msg]
    assert len(kind_records) == 1
