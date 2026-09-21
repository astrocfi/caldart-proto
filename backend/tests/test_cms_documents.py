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
from collections.abc import Iterator
from io import StringIO
from pathlib import Path
from typing import cast

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.http import HttpResponse, HttpResponseBase, StreamingHttpResponse
from django.test import Client
from pytest_django.fixtures import Settings
from wagtail.documents import get_document_model
from wagtail.documents.models import Document as WagtailDocument
from wagtail.models import Collection

from apps.accounts.models import User
from apps.cms.models import (
    MEMBERS_ONLY_COLLECTION_NAME,
    SiteSettings,
    StandardPage,
    ensure_members_only_collection,
)
from apps.members.models import MembershipPlan
from tests.test_cms_pages import expire_membership, grant_membership
from tests.test_sysadmin_settings import DEPLOY

pytestmark = pytest.mark.django_db

Document = get_document_model()

#: The bytes of the guarded file; no refusal may contain them.
SECRET = b"%PDF-1.4 the member roster"

APACHE = DEPLOY / "apache" / "caldart.conf"
NGINX = DEPLOY / "nginx" / "caldart.conf"


def make_document(collection: Collection, *, title: str = "Member roster") -> WagtailDocument:
    """Upload ``SECRET`` into ``collection`` under a fixed filename and return it."""
    return Document.objects.create(
        title=title,
        file=ContentFile(SECRET, name="roster.pdf"),
        collection=collection,
    )


def body_of(response: HttpResponseBase) -> bytes:
    """The response body, whether it streams (a served file) or not (the wall)."""
    # The test client's stub loses the real response subclass (it monkeypatches
    # the class Wagtail's view returns), so mypy only sees the common base here;
    # `.streaming` at runtime says which real type each response actually is.
    if response.streaming:
        streaming_content = cast(StreamingHttpResponse, response).streaming_content
        return b"".join(cast(Iterator[bytes], streaming_content))
    return cast(HttpResponse, response).content


def config_text(config: Path) -> str:
    """A proxy config with its comments stripped, so only what it *does* is matched."""
    lines = config.read_text().splitlines()
    return "\n".join(line for line in lines if not line.strip().startswith("#"))


@pytest.fixture(autouse=True)
def document_storage(settings: Settings, tmp_path: Path) -> None:
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
def members_collection(db: None) -> Collection:
    """The "Members only" document collection, created if it does not exist."""
    return ensure_members_only_collection()


@pytest.fixture
def members_document(members_collection: Collection) -> WagtailDocument:
    """A document uploaded into the members-only collection."""
    return make_document(members_collection)


# ------------------------------------------------------------ who is refused
def test_an_anonymous_visitor_is_refused(
    client: Client, site_settings: SiteSettings, members_document: WagtailDocument
) -> None:
    """An anonymous visitor downloading a members-only document gets a 403."""
    assert client.get(members_document.url).status_code == 403


def test_a_refusal_withholds_the_file(
    client: Client, site_settings: SiteSettings, members_document: WagtailDocument
) -> None:
    """A refused download never contains the guarded file's bytes."""
    assert SECRET not in body_of(client.get(members_document.url))


def test_a_refusal_renders_the_members_only_wall(
    client: Client, site_settings: SiteSettings, members_document: WagtailDocument
) -> None:
    """A refused document download renders the members-only wall's sign-in link."""
    body = body_of(client.get(members_document.url)).decode()
    assert "/portal/login?next=" in body


def test_the_wall_names_the_document(
    client: Client, site_settings: SiteSettings, members_document: WagtailDocument
) -> None:
    """The members-only wall names the document the visitor tried to download."""
    body = body_of(client.get(members_document.url)).decode()
    assert "Member roster" in body


def test_a_member_whose_membership_lapsed_is_refused(
    client: Client,
    site_settings: SiteSettings,
    members_document: WagtailDocument,
    member: User,
    annual_plan: MembershipPlan,
) -> None:
    """A member whose term expired is refused a members-only document."""
    expire_membership(member, annual_plan)
    client.force_login(member)

    assert client.get(members_document.url).status_code == 403


def test_a_lapsed_member_is_offered_renewal(
    client: Client,
    site_settings: SiteSettings,
    members_document: WagtailDocument,
    member: User,
    annual_plan: MembershipPlan,
) -> None:
    """A member whose term expired is offered a renewal link on the wall."""
    expire_membership(member, annual_plan)
    client.force_login(member)

    assert "/portal/renew" in body_of(client.get(members_document.url)).decode()


def test_a_member_who_never_paid_is_refused(
    client: Client, site_settings: SiteSettings, members_document: WagtailDocument, member: User
) -> None:
    """A signed-in user with no membership at all is refused the document."""
    client.force_login(member)

    assert client.get(members_document.url).status_code == 403


# ------------------------------------------------------------- who is served
def test_a_current_member_is_served_the_file(
    client: Client,
    site_settings: SiteSettings,
    members_document: WagtailDocument,
    member: User,
    annual_plan: MembershipPlan,
) -> None:
    """A member with a current term downloads the exact file bytes."""
    grant_membership(member, annual_plan)
    client.force_login(member)

    assert body_of(client.get(members_document.url)) == SECRET


def test_a_dart_leader_without_a_membership_is_served_the_file(
    client: Client, site_settings: SiteSettings, members_document: WagtailDocument, leader: User
) -> None:
    """A DART leader with no membership of their own still downloads the file."""
    assert leader.membership_status["status"] == "none"
    client.force_login(leader)

    assert body_of(client.get(members_document.url)) == SECRET


# ------------------------------------------------- which collections are closed
def test_a_child_collection_is_guarded_too(
    client: Client, site_settings: SiteSettings, members_collection: Collection
) -> None:
    """A document in a collection nested under "Members only" is guarded too."""
    child = members_collection.add_child(name="Board minutes")
    document = make_document(child, title="Minutes")

    assert client.get(document.url).status_code == 403


def test_a_document_in_the_root_collection_stays_public(
    client: Client, site_settings: SiteSettings
) -> None:
    """A document in the root collection downloads without signing in."""
    document = make_document(Collection.get_first_root_node(), title="Sponsor flyer")

    assert body_of(client.get(document.url)) == SECRET


def test_a_sibling_collection_stays_public(client: Client, site_settings: SiteSettings) -> None:
    """A document outside "Members only" and its children stays public."""
    other = Collection.get_first_root_node().add_child(name="Press kit")
    document = make_document(other, title="Logo pack")

    assert body_of(client.get(document.url)) == SECRET


# -------------------------------------------------------------- the serve path
def test_documents_are_served_through_django() -> None:
    """``WAGTAILDOCS_SERVE_METHOD`` routes document downloads through Django."""
    assert settings.WAGTAILDOCS_SERVE_METHOD == "serve_view"


def test_a_document_url_does_not_point_at_media(members_document: WagtailDocument) -> None:
    """A document's URL is served from ``/documents/``, never ``/media/``."""
    assert members_document.url.startswith("/documents/")


# --------------------------------------------------------------------- the seed
def test_the_seed_creates_the_members_only_collection() -> None:
    """``seed_content`` creates exactly one "Members only" collection."""
    call_command("seed_content", stdout=StringIO())

    assert Collection.objects.filter(name=MEMBERS_ONLY_COLLECTION_NAME).count() == 1


def test_seeding_twice_leaves_one_collection() -> None:
    """Running ``seed_content`` twice does not duplicate the collection."""
    call_command("seed_content", stdout=StringIO())
    call_command("seed_content", stdout=StringIO())

    assert Collection.objects.filter(name=MEMBERS_ONLY_COLLECTION_NAME).count() == 1


def test_the_seeded_collection_sits_under_the_root() -> None:
    """The seeded "Members only" collection is a direct child of the root collection."""
    call_command("seed_content", stdout=StringIO())

    collection = Collection.objects.get(name=MEMBERS_ONLY_COLLECTION_NAME)
    assert collection.get_parent() == Collection.get_first_root_node()


def test_the_documents_page_says_where_to_upload_members_only_files() -> None:
    """The seeded documents-and-links page names the members-only collection."""
    call_command("seed_content", stdout=StringIO())

    page = StandardPage.objects.get(slug="docs-and-links")
    copy = " ".join(str(block.value) for block in page.body)
    assert MEMBERS_ONLY_COLLECTION_NAME in copy


# ------------------------------------------------------------------ the proxies
def test_nginx_refuses_the_documents_directory() -> None:
    """The nginx config returns 404 for any request under ``/media/documents/``."""
    pattern = r"location\s+/media/documents/\s*\{[^}]*return\s+404;"
    assert re.search(pattern, config_text(NGINX)) is not None


def test_apache_refuses_the_documents_directory() -> None:
    """The Apache config denies all access to the documents media directory."""
    pattern = (
        r"<Directory\s+\"?/srv/caldart/backend/media/documents\"?\s*>"
        r"[^<]*Require\s+all\s+denied"
    )
    assert re.search(pattern, config_text(APACHE)) is not None


def test_apache_no_longer_calls_the_uploads_public() -> None:
    """The Apache config no longer describes uploads as public by design."""
    assert "public by design" not in APACHE.read_text()
