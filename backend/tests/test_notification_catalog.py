"""The notification catalog agrees with the project's event list and is complete."""

from __future__ import annotations

import pytest

from apps.accounts.roles import ROLE_SLUGS
from apps.notifications.events import CATEGORIES, EVENTS
from caldart.events import EVENT_SLUGS


def test_the_catalog_lists_exactly_the_events_the_project_raises_in_order() -> None:
    """``EVENTS`` and ``caldart.events.EVENT_SLUGS`` name the same slugs, in order."""
    assert tuple(EVENTS) == EVENT_SLUGS


@pytest.mark.parametrize("slug", EVENT_SLUGS)
def test_each_event_has_a_label_a_category_a_description_and_roles(slug: str) -> None:
    """Every event carries the words the screen shows and at least one role."""
    event = EVENTS[slug]
    assert event.slug == slug
    assert event.label != ""
    assert event.category in CATEGORIES
    assert event.description.endswith(".")
    assert len(event.roles) > 0


@pytest.mark.parametrize("slug", EVENT_SLUGS)
def test_each_role_an_event_names_is_a_real_role(slug: str) -> None:
    """The roles that may receive an event are role slugs the accounts app knows."""
    assert set(EVENTS[slug].roles) <= set(ROLE_SLUGS)


def test_the_purpose_is_the_slug_under_a_notification_prefix() -> None:
    """An event's email log purpose is ``notification_<slug>``."""
    assert EVENTS["signed_up"].purpose == "notification_signed_up"


def test_every_category_lists_at_least_one_event() -> None:
    """No category heading on the screen is empty."""
    assert {event.category for event in EVENTS.values()} == set(CATEGORIES)
