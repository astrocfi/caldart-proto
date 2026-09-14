"""Documents in the Members-only collection are guarded like a members-only page.

``apps.cms.wagtail_hooks`` registers a ``before_serve_document`` hook: a download
from the "Members only" collection, or from any collection beneath it, is answered
with the members-only wall and HTTP 403 unless the reader passes
``user_can_access_members_content``.  Documents in every other collection stay
public.  ``WAGTAILDOCS_SERVE_METHOD`` keeps document URLs pointed at Django, and
both proxies refuse ``/media/documents/``, so the files on disk are reachable only
through the guarded view.
"""

from __future__ import annotations

import re
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from wagtail.documents import get_document_model
from wagtail.models import Collection

from apps.cms.models import (
    MEMBERS_ONLY_COLLECTION_NAME,
    StandardPage,
    ensure_members_only_collection,
)
from tests.test_cms_pages import expire_membership, grant_membership
from tests.test_sysadmin_settings import DEPLOY

pytestmark = pytest.mark.django_db

Document = get_document_model()

#: The bytes of the guarded file; no refusal may contain them.
SECRET = b"%PDF-1.4 the member roster"

APACHE = DEPLOY / "apache" / "caldart.conf"
NGINX = DEPLOY / "nginx" / "caldart.conf"


def make_document(collection: Collection, *, title: str = "Member roster") -> Document:
    """Upload ``SECRET`` into ``collection`` under a fixed filename."""
    return Document.objects.create(
        title=title,
        file=ContentFile(SECRET, name="roster.pdf"),
        collection=collection,
    )


def body_of(response) -> bytes:
    """The response body, whether it streams (a served file) or not (the wall)."""
    if response.streaming:
        return b"".join(response.streaming_content)
    return response.content


def config_text(config: Path) -> str:
    """A proxy config with its comments stripped, so only what it *does* is matched."""
    lines = config.read_text().splitlines()
    return "\n".join(line for line in lines if not line.strip().startswith("#"))


@pytest.fixture(autouse=True)
def document_storage(settings, tmp_path) -> None:
    """Store uploads on a real filesystem, as the deployed site does.

    The suite's default in-memory storage has no readable path, so the serve
    view cannot stream a file back from it.
    """
    settings.MEDIA_ROOT = tmp_path
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    }


@pytest.fixture
def members_collection(db) -> Collection:
    return ensure_members_only_collection()


@pytest.fixture
def members_document(members_collection) -> Document:
    return make_document(members_collection)


# ------------------------------------------------------------ who is refused
def test_an_anonymous_visitor_is_refused(client, site_settings, members_document) -> None:
    assert client.get(members_document.url).status_code == 403


def test_a_refusal_withholds_the_file(client, site_settings, members_document) -> None:
    assert SECRET not in body_of(client.get(members_document.url))


def test_a_refusal_renders_the_members_only_wall(client, site_settings, members_document) -> None:
    body = body_of(client.get(members_document.url)).decode()
    assert "/portal/login?next=" in body


def test_the_wall_names_the_document(client, site_settings, members_document) -> None:
    body = body_of(client.get(members_document.url)).decode()
    assert "Member roster" in body


def test_a_member_whose_membership_lapsed_is_refused(
    client, site_settings, members_document, member, annual_plan
) -> None:
    expire_membership(member, annual_plan)
    client.force_login(member)

    assert client.get(members_document.url).status_code == 403


def test_a_lapsed_member_is_offered_renewal(
    client, site_settings, members_document, member, annual_plan
) -> None:
    expire_membership(member, annual_plan)
    client.force_login(member)

    assert "/portal/renew" in body_of(client.get(members_document.url)).decode()


def test_a_member_who_never_paid_is_refused(
    client, site_settings, members_document, member
) -> None:
    client.force_login(member)

    assert client.get(members_document.url).status_code == 403


# ------------------------------------------------------------- who is served
def test_a_current_member_is_served_the_file(
    client, site_settings, members_document, member, annual_plan
) -> None:
    grant_membership(member, annual_plan)
    client.force_login(member)

    assert body_of(client.get(members_document.url)) == SECRET


def test_a_dart_leader_without_a_membership_is_served_the_file(
    client, site_settings, members_document, leader
) -> None:
    assert leader.membership_status["status"] == "none"
    client.force_login(leader)

    assert body_of(client.get(members_document.url)) == SECRET


# ------------------------------------------------- which collections are closed
def test_a_child_collection_is_guarded_too(client, site_settings, members_collection) -> None:
    child = members_collection.add_child(name="Board minutes")
    document = make_document(child, title="Minutes")

    assert client.get(document.url).status_code == 403


def test_a_document_in_the_root_collection_stays_public(client, site_settings) -> None:
    document = make_document(Collection.get_first_root_node(), title="Sponsor flyer")

    assert body_of(client.get(document.url)) == SECRET


def test_a_sibling_collection_stays_public(client, site_settings) -> None:
    other = Collection.get_first_root_node().add_child(name="Press kit")
    document = make_document(other, title="Logo pack")

    assert body_of(client.get(document.url)) == SECRET


# -------------------------------------------------------------- the serve path
def test_documents_are_served_through_django() -> None:
    assert settings.WAGTAILDOCS_SERVE_METHOD == "serve_view"


def test_a_document_url_does_not_point_at_media(members_document) -> None:
    assert members_document.url.startswith("/documents/")


# --------------------------------------------------------------------- the seed
def test_the_seed_creates_the_members_only_collection() -> None:
    call_command("seed_content", stdout=StringIO())

    assert Collection.objects.filter(name=MEMBERS_ONLY_COLLECTION_NAME).count() == 1


def test_seeding_twice_leaves_one_collection() -> None:
    call_command("seed_content", stdout=StringIO())
    call_command("seed_content", stdout=StringIO())

    assert Collection.objects.filter(name=MEMBERS_ONLY_COLLECTION_NAME).count() == 1


def test_the_seeded_collection_sits_under_the_root() -> None:
    call_command("seed_content", stdout=StringIO())

    collection = Collection.objects.get(name=MEMBERS_ONLY_COLLECTION_NAME)
    assert collection.get_parent() == Collection.get_first_root_node()


def test_the_documents_page_says_where_to_upload_members_only_files() -> None:
    call_command("seed_content", stdout=StringIO())

    page = StandardPage.objects.get(slug="docs-and-links")
    copy = " ".join(str(block.value) for block in page.body)
    assert MEMBERS_ONLY_COLLECTION_NAME in copy


# ------------------------------------------------------------------ the proxies
def test_nginx_refuses_the_documents_directory() -> None:
    pattern = r"location\s+/media/documents/\s*\{[^}]*return\s+404;"
    assert re.search(pattern, config_text(NGINX)) is not None


def test_apache_refuses_the_documents_directory() -> None:
    pattern = (
        r"<Directory\s+\"?/srv/caldart/backend/media/documents\"?\s*>"
        r"[^<]*Require\s+all\s+denied"
    )
    assert re.search(pattern, config_text(APACHE)) is not None


def test_apache_no_longer_calls_the_uploads_public() -> None:
    assert "public by design" not in APACHE.read_text()
