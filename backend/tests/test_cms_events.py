"""The event calendar: the index, one event's page, and what the sidebar reads.

The home page's own use of the calendar is covered in ``test_cms_pages.py``;
this file covers the pages themselves.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.cms.models import EventIndexPage, EventPage, SiteSettings
from tests.factories import make_event_index, make_event_page

pytestmark = pytest.mark.django_db


@pytest.fixture
def calendar(site_settings: SiteSettings) -> EventIndexPage:
    """An event index under the site root, with nothing below it yet."""
    return make_event_index(site_settings.site.root_page.specific)


def test_upcoming_lists_the_events_still_ahead_soonest_first(calendar: EventIndexPage) -> None:
    """``upcoming`` is date order, and today counts as still ahead."""
    make_event_page(calendar, "spring", "Spring exercise", days_ahead=90)
    make_event_page(calendar, "today", "Ramp session", days_ahead=0)
    make_event_page(calendar, "radio", "Radio drill", days_ahead=30)

    assert [event.title for event in calendar.upcoming()] == [
        "Ramp session",
        "Radio drill",
        "Spring exercise",
    ]


def test_upcoming_leaves_out_what_has_already_happened(calendar: EventIndexPage) -> None:
    """Yesterday's event is not upcoming, however recent it was."""
    make_event_page(calendar, "yesterday", "Tabletop exercise", days_ahead=-1)
    assert list(calendar.upcoming()) == []


def test_past_lists_what_has_happened_most_recent_first(calendar: EventIndexPage) -> None:
    """``past`` runs backwards from yesterday."""
    make_event_page(calendar, "old", "Last year's drill", days_ahead=-300)
    make_event_page(calendar, "recent", "Tabletop exercise", days_ahead=-4)
    make_event_page(calendar, "ahead", "Radio drill", days_ahead=30)

    assert [event.title for event in calendar.past()] == ["Tabletop exercise", "Last year's drill"]


def test_an_unpublished_event_is_in_neither_list(calendar: EventIndexPage) -> None:
    """A draft is invisible until it is published."""
    event = make_event_page(calendar, "draft", "Draft workshop", days_ahead=10)
    event.unpublish()

    assert list(calendar.upcoming()) == []


def test_the_index_renders_both_lists(client: Client, calendar: EventIndexPage) -> None:
    """The calendar page shows what is coming and what has happened, with links."""
    ahead = make_event_page(calendar, "radio", "Radio drill", days_ahead=30)
    make_event_page(calendar, "tabletop", "Tabletop exercise", days_ahead=-4)

    body = client.get(calendar.url or "/events/").content.decode()

    assert "Coming up" in body
    assert "Already happened" in body
    assert f'href="{ahead.url}"' in body


def test_the_index_says_so_when_nothing_is_coming_up(
    client: Client, calendar: EventIndexPage
) -> None:
    """An empty calendar reads as empty rather than as a broken page."""
    body = client.get(calendar.url or "/events/").content.decode()
    assert "Nothing on the calendar yet" in body


def test_an_event_page_shows_when_and_where_it_is(client: Client, calendar: EventIndexPage) -> None:
    """The time and the place are printed as one line above the lede."""
    event = make_event_page(
        calendar,
        "workshop",
        "Ground crew workshop",
        days_ahead=12,
        time="9 am to 1 pm",
        location="Reid-Hillview (KRHV)",
        intro="Manifests, weight and balance, and safe loading.",
    )

    body = client.get(event.url or "/events/workshop/").content.decode()

    assert "Reid-Hillview (KRHV), 9 am to 1 pm" in body
    assert "Manifests, weight and balance, and safe loading." in body


def test_when_and_where_reads_whichever_half_is_set(calendar: EventIndexPage) -> None:
    """A place with no time reads as the place alone."""
    event = make_event_page(calendar, "meeting", "Leaders meeting", location="San Martin (E16)")
    assert event.when_and_where == "San Martin (E16)"


def test_when_and_where_is_empty_when_neither_is_set(calendar: EventIndexPage) -> None:
    """Neither half gives an empty string, so the template prints nothing."""
    event = make_event_page(calendar, "meeting", "Leaders meeting")
    assert event.when_and_where == ""


def test_a_past_event_says_so_on_its_own_page(client: Client, calendar: EventIndexPage) -> None:
    """An event whose day is over is marked, so a stale link is not misread."""
    event = make_event_page(calendar, "tabletop", "Tabletop exercise", days_ahead=-4)

    assert event.is_past is True
    assert "Already happened" in client.get(event.url or "/events/tabletop/").content.decode()


def test_an_event_today_is_not_past(calendar: EventIndexPage) -> None:
    """Today's event has not happened until the day is over."""
    event = make_event_page(calendar, "today", "Ramp session", days_ahead=0)
    assert event.is_past is False


def test_the_index_paginates_what_has_already_happened(
    client: Client, calendar: EventIndexPage
) -> None:
    """Past events page at ``EVENT_PAGE_SIZE``; the second page holds the remainder."""
    from apps.cms.models import EVENT_PAGE_SIZE

    for index in range(EVENT_PAGE_SIZE + 1):
        make_event_page(calendar, f"past-{index}", f"Drill {index}", days_ahead=-(index + 1))

    response = client.get(f"{calendar.url}?page=2")

    assert response.context["past"].number == 2
    assert len(response.context["past"].object_list) == 1


def test_a_date_in_the_future_is_what_the_sidebar_reads(calendar: EventIndexPage) -> None:
    """``EventPage.objects.upcoming`` is the query the home page's sidebar uses."""
    today = timezone.localdate()
    make_event_page(calendar, "radio", "Radio drill", days_ahead=30)

    assert [event.date for event in EventPage.objects.upcoming()] == [today + timedelta(days=30)]
