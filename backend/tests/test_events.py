"""The event module: a closed list of slugs, and handlers that hear every emit."""

from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest

from caldart import events


@pytest.fixture
def recorded() -> Iterator[list[tuple[str, Mapping[str, object]]]]:
    """Every event raised while the test runs, as ``(slug, payload)`` pairs."""
    seen: list[tuple[str, Mapping[str, object]]] = []

    def record(slug: str, payload: Mapping[str, object]) -> None:
        seen.append((slug, payload))

    events.subscribe(record)
    yield seen
    events.unsubscribe(record)


def test_a_handler_receives_the_slug_and_the_payload(
    recorded: list[tuple[str, Mapping[str, object]]],
) -> None:
    """``emit`` hands each handler the slug and the keyword arguments as a mapping."""
    events.emit("signed_up", user="ada", dart=None)

    assert recorded == [("signed_up", {"user": "ada", "dart": None})]


def test_an_unknown_slug_is_refused_before_any_handler_runs(
    recorded: list[tuple[str, Mapping[str, object]]],
) -> None:
    """A slug outside ``EVENT_SLUGS`` raises ``ValueError`` and reaches no handler."""
    with pytest.raises(ValueError, match="Unknown event 'signed_upp'"):
        events.emit("signed_upp", user="ada")

    assert recorded == []


def test_handlers_run_in_registration_order() -> None:
    """Two handlers hear one event in the order they subscribed."""
    order: list[str] = []

    def first(slug: str, payload: Mapping[str, object]) -> None:
        order.append("first")

    def second(slug: str, payload: Mapping[str, object]) -> None:
        order.append("second")

    events.subscribe(first)
    events.subscribe(second)
    try:
        events.emit("member_added", user="ada")
    finally:
        events.unsubscribe(first)
        events.unsubscribe(second)

    assert order == ["first", "second"]


def test_subscribing_twice_registers_once() -> None:
    """The same handler subscribed twice hears an event once."""
    calls: list[str] = []

    def once(slug: str, payload: Mapping[str, object]) -> None:
        calls.append(slug)

    events.subscribe(once)
    events.subscribe(once)
    try:
        events.emit("aircraft_added", aircraft="N1")
    finally:
        events.unsubscribe(once)

    assert calls == ["aircraft_added"]


def test_unsubscribing_an_unknown_handler_leaves_the_others_in_place() -> None:
    """``unsubscribe`` of a handler never registered raises nothing, removes nothing."""
    calls: list[str] = []

    def kept(slug: str, payload: Mapping[str, object]) -> None:
        calls.append(slug)

    def never(slug: str, payload: Mapping[str, object]) -> None:
        return None

    events.subscribe(kept)
    try:
        events.unsubscribe(never)
        events.emit("roles_changed", user="ada")
    finally:
        events.unsubscribe(kept)

    assert calls == ["roles_changed"]


def test_the_slugs_are_unique_and_snake_case() -> None:
    """Every slug is distinct and made of lowercase words joined by underscores."""
    assert len(set(events.EVENT_SLUGS)) == len(events.EVENT_SLUGS)
    assert all(slug.replace("_", "a").isalpha() and slug.islower() for slug in events.EVENT_SLUGS)
