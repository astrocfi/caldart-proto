"""Two confirmations of one payment arriving at the same moment.

The webhook and the browser's own confirmation both call ``mark_succeeded``, and
nothing orders them.  ``mark_succeeded`` re-reads the payment with
``select_for_update``, so the second caller waits at the row until the first has
committed and then finds a payment that has already succeeded: it returns
without writing the row or activating anything a second time.  These tests run
that collision for real, in two threads against the live database.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest
from django.db import connections

from apps.accounts.models import User
from apps.members.models import Membership, MembershipPlan
from apps.members.services import activate_term
from apps.payments import services as payment_services
from apps.payments.models import Payment, PaymentStatus
from apps.payments.services import create_checkout, mark_succeeded

# The threads must see each other's committed rows, so this module runs against
# a real, committing database rather than the usual wrapping transaction.
pytestmark = pytest.mark.django_db(transaction=True)

#: How long the first confirmation holds the payment inside its transaction.
#: Long enough that the second caller reaches the row while the first still
#: holds it, so a read taken without the lock really would see ``pending``.
HOLD_SECONDS = 0.3

#: How long a thread waits for its partner at the barrier, and the test for the
#: threads, before giving up rather than hanging the suite.
JOIN_TIMEOUT_SECONDS = 30.0


@pytest.fixture
def activations(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Record each term activation, holding the caller in its transaction while it runs.

    The returned list grows by the payment's id every time ``mark_succeeded`` gets
    as far as activating a term, which is the step the second caller must not
    reach.  The hold widens the window the lock has to close.
    """
    calls: list[int] = []

    def held_activate_term(*args: Any, **kwargs: Any) -> Membership:
        payment = kwargs["payment"]
        calls.append(payment.pk)
        time.sleep(HOLD_SECONDS)
        return activate_term(*args, **kwargs)

    monkeypatch.setattr(payment_services, "activate_term", held_activate_term)
    return calls


def confirm_in_thread(payment_pk: int, start: threading.Barrier, failures: list[str]) -> None:
    """Confirm the payment as soon as the other thread is ready, recording any error."""
    try:
        start.wait(timeout=JOIN_TIMEOUT_SECONDS)
        mark_succeeded(Payment.objects.get(pk=payment_pk), provider_ref="pi_race")
    # A thread's exception would otherwise be printed and lost; the test asserts
    # on what it caught instead.
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")
    finally:
        # Each thread opened its own connection; leaving it open would keep the
        # test database busy and stall the teardown that flushes the tables.
        connections.close_all()


def confirm_twice_at_once(payment: Payment) -> list[str]:
    """Run two confirmations of ``payment`` in parallel, returning what they raised."""
    start = threading.Barrier(2)
    failures: list[str] = []
    threads = [
        threading.Thread(target=confirm_in_thread, args=(payment.pk, start, failures))
        for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=JOIN_TIMEOUT_SECONDS)
    assert [thread.is_alive() for thread in threads] == [False, False]
    return failures


@pytest.fixture
def racing_checkout(member: User, annual_plan: MembershipPlan) -> Payment:
    """A pending payment for one annual membership, ready to be confirmed twice."""
    return create_checkout(member, annual_plan.slug)


def test_the_second_confirmation_does_not_reach_the_activation(
    racing_checkout: Payment, activations: list[int]
) -> None:
    """Only the caller that wins the row activates a term; the other returns early."""
    failures = confirm_twice_at_once(racing_checkout)

    assert failures == []
    assert activations == [racing_checkout.pk]


def test_two_simultaneous_confirmations_grant_one_term(
    racing_checkout: Payment, activations: list[int]
) -> None:
    """Two threads confirming one payment at once leave exactly one membership term."""
    confirm_twice_at_once(racing_checkout)

    assert Membership.objects.count() == 1


def test_two_simultaneous_confirmations_leave_one_succeeded_payment(
    racing_checkout: Payment, activations: list[int]
) -> None:
    """The collision ends with the payment succeeded, completed and referenced once."""
    confirm_twice_at_once(racing_checkout)

    racing_checkout.refresh_from_db()
    assert racing_checkout.status == PaymentStatus.SUCCEEDED
    assert racing_checkout.provider_ref == "pi_race"
    assert Payment.objects.filter(status=PaymentStatus.SUCCEEDED).count() == 1


def test_the_member_is_covered_by_the_one_term_the_collision_left(
    racing_checkout: Payment, member: User, activations: list[int]
) -> None:
    """The member ends the collision with one term, not two stacked back to back."""
    confirm_twice_at_once(racing_checkout)

    assert [term.payment_id for term in member.memberships.all()] == [racing_checkout.pk]
