"""A verifier's stamp and the owner's own edit, arriving at the same record at once.

``verify_member`` and ``verify_insurance`` lock the record with ``select_for_update``
before reading it, and so do ``ProfileSerializer.update`` (``PATCH /me/profile``) and
``AircraftDetailView.perform_update`` (``PATCH /aircraft/{id}``) -- the two paths an
owner's own edit takes.  Without the lock, a verifier who stamps an item while the
owner's edit to the same fields is mid-flight can read the record before the other
write lands, so the two saves combine into a value verified as current that neither
request actually saw: the item ends up verified, but showing the edited value.  With
the lock, the edit waits for the verifier's transaction to commit, then finds the item
verified against the value it is about to move away from, and clears it.  These tests
run that collision for real, in two threads against the live database.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

import pytest
from django.db import connections
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.aircraft import services as aircraft_services
from apps.aircraft.models import Aircraft
from apps.aircraft.verification import verify_insurance
from apps.members import verification as member_verification
from apps.members.models import MemberProfile, PilotCertificateType
from apps.members.verification import verify_member
from tests.factories import AircraftFactory, MemberProfileFactory

# The two threads must see each other's committed rows, so this module runs against
# a real, committing database rather than the usual wrapping transaction.
pytestmark = pytest.mark.django_db(transaction=True)

PROFILE_URL = "/api/v1/me/profile"

#: Long enough that the waiting thread has reached the lock before the holder commits,
#: so a read taken without the lock really would see the pre-collision value.
HOLD_SECONDS = 0.3

#: How long a thread waits for its partner, and the test for the threads, before
#: giving up rather than hanging the suite.
JOIN_TIMEOUT_SECONDS = 30.0


@pytest.fixture
def held_member_verify(monkeypatch: pytest.MonkeyPatch) -> threading.Event:
    """Hold ``verify_member`` right after it locks the profile row, before any write.

    ``verified_items`` is the first thing ``verify_member`` calls once it has the row;
    nothing else in the module calls it, so the hold cannot fire for the concurrent
    edit.  Signals the returned event, then sleeps, holding the transaction (and, once
    the row is locked with ``select_for_update``, the lock) open long enough for a
    concurrent edit to reach the same row and queue behind it.
    """
    locked = threading.Event()
    real_verified_items = member_verification.verified_items

    def held_verified_items(profile: MemberProfile) -> list[str]:
        locked.set()
        time.sleep(HOLD_SECONDS)
        return real_verified_items(profile)

    monkeypatch.setattr(member_verification, "verified_items", held_verified_items)
    return locked


@pytest.fixture
def held_aircraft_verify(monkeypatch: pytest.MonkeyPatch) -> threading.Event:
    """Hold ``verify_insurance`` right after it locks the row, before any write.

    ``changed_fields`` is the first thing ``verify_insurance`` calls once it has the
    row; the concurrent edit calls it too, but always with fields to compare, so the
    hold fires only for the empty check ``verify_insurance`` makes when it is only
    stamping, not changing a field.  Signals the returned event, then sleeps, holding
    the transaction (and, once the row is locked with ``select_for_update``, the lock)
    open long enough for the edit to reach the same row and queue behind it.
    """
    locked = threading.Event()
    real_changed_fields = aircraft_services.changed_fields

    def held_changed_fields(aircraft: Aircraft, validated: dict[str, Any]) -> list[str]:
        if len(validated) == 0:
            locked.set()
            time.sleep(HOLD_SECONDS)
        return real_changed_fields(aircraft, validated)

    monkeypatch.setattr(aircraft_services, "changed_fields", held_changed_fields)
    return locked


def run_in_thread(target: Callable[[], None], failures: list[str]) -> threading.Thread:
    """Start ``target`` in a thread that records any exception into ``failures``."""

    def wrapped() -> None:
        try:
            target()
        # A thread's exception would otherwise be printed and lost; the test asserts
        # on what it caught instead.
        except Exception as exc:
            failures.append(f"{type(exc).__name__}: {exc}")
        finally:
            # Each thread opened its own connection; leaving it open would keep the
            # test database busy and stall the teardown that flushes the tables.
            connections.close_all()

    thread = threading.Thread(target=wrapped)
    thread.start()
    return thread


def test_a_profile_edit_that_arrives_mid_verify_clears_the_stamp_it_raced(
    dart_leader: User,
    member: User,
    held_member_verify: threading.Event,
) -> None:
    """The lock makes the edit wait, so it sees -- and clears -- the stamp it raced.

    Without the lock, the edit's unlocked read would still show the certificate
    unverified, so it would write the new number without touching the verification
    columns; the verifier's later save would then leave the certificate verified
    against a certificate number it never saw.
    """
    profile = MemberProfileFactory(
        user=member,
        pilot_certificate_type=PilotCertificateType.PRIVATE,
        certificate_number="1234567",
    )
    api_client = APIClient()
    api_client.force_authenticate(user=member)
    failures: list[str] = []

    def do_verify() -> None:
        verify_member(dart_leader, member, changes={}, verified=["certificate"])

    def do_edit() -> None:
        held_member_verify.wait(timeout=JOIN_TIMEOUT_SECONDS)
        response = api_client.patch(PROFILE_URL, {"certificate_number": "7654321"}, format="json")
        assert response.status_code == 200

    threads = [run_in_thread(do_verify, failures), run_in_thread(do_edit, failures)]
    for thread in threads:
        thread.join(timeout=JOIN_TIMEOUT_SECONDS)

    assert [thread.is_alive() for thread in threads] == [False, False]
    assert failures == []
    profile.refresh_from_db()
    assert profile.certificate_number == "7654321"
    assert profile.certificate_is_verified is False


def test_an_aircraft_edit_that_arrives_mid_verify_clears_the_stamp_it_raced(
    dart_leader: User,
    member: User,
    held_aircraft_verify: threading.Event,
) -> None:
    """The lock makes the edit wait, so it sees -- and clears -- the stamp it raced.

    Without the lock, the edit's unlocked read would still show the insurance
    unverified, so it would write the new carrier without touching the verification
    columns; the verifier's later save would then leave the insurance verified
    against a carrier it never saw.
    """
    aircraft = AircraftFactory(created_by=member, insurance_carrier="Old Mutual")
    api_client = APIClient()
    api_client.force_authenticate(user=member)
    failures: list[str] = []

    def do_verify() -> None:
        verify_insurance(aircraft, actor=dart_leader, changes={}, verified=True)

    def do_edit() -> None:
        held_aircraft_verify.wait(timeout=JOIN_TIMEOUT_SECONDS)
        response = api_client.patch(
            f"/api/v1/aircraft/{aircraft.pk}", {"insurance_carrier": "New Mutual"}, format="json"
        )
        assert response.status_code == 200

    threads = [run_in_thread(do_verify, failures), run_in_thread(do_edit, failures)]
    for thread in threads:
        thread.join(timeout=JOIN_TIMEOUT_SECONDS)

    assert [thread.is_alive() for thread in threads] == [False, False]
    assert failures == []
    aircraft.refresh_from_db()
    assert aircraft.insurance_carrier == "New Mutual"
    assert aircraft.insurance_is_verified is False
