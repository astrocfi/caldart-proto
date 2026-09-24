"""The home page's team finder: ``/find-dart/`` turns a chosen DART into a page."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.cms.models import SiteSettings
from apps.darts.models import Dart
from tests.factories import (
    make_dart_index,
    make_dart_page,
    make_standard_page,
)

pytestmark = pytest.mark.django_db

URL = "/find-dart/"


@pytest.fixture
def dart_index_url(site_settings: SiteSettings) -> str:
    """Build About Us and the DART directory below it, and return the directory's path."""
    home = site_settings.site.root_page.specific
    about = make_standard_page(home, "about", "About Us")
    index = make_dart_index(about)
    return str(index.url)


def test_a_chosen_dart_leads_to_its_own_page(
    client: Client, dart_index_url: str, dart: Dart
) -> None:
    """Choosing a DART that has a published page lands on that page."""
    home = SiteSettings.objects.get().site.root_page.specific
    index = home.dart_index
    page = make_dart_page(index, dart)

    response = client.get(URL, {"dart": str(dart.pk)})

    assert response.status_code == 302
    assert response.headers["Location"] == page.url


def test_a_dart_without_a_page_falls_back_to_the_directory(
    client: Client, dart_index_url: str, dart: Dart
) -> None:
    """A team nobody has written a page for sends the reader to the directory."""
    response = client.get(URL, {"dart": str(dart.pk)})

    assert response.status_code == 302
    assert response.headers["Location"] == dart_index_url


@pytest.mark.parametrize(
    "value",
    ["", "0", "not-a-number", "../../etc/passwd", "https://example.org/"],
    ids=["empty", "unknown", "text", "traversal", "absolute-url"],
)
def test_an_unusable_choice_falls_back_to_the_directory(
    client: Client, dart_index_url: str, value: str
) -> None:
    """A missing, unknown or hostile value never leaves the site."""
    response = client.get(URL, {"dart": value})

    assert response.status_code == 302
    assert response.headers["Location"] == dart_index_url


def test_without_a_directory_the_reader_goes_home(client: Client, dart: Dart) -> None:
    """With no DART directory published, the finder falls back to the site root."""
    response = client.get(URL, {"dart": str(dart.pk)})

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
