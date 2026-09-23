"""Plain Django views the public site needs alongside Wagtail's page serving.

Wagtail answers every content URL; this module holds the one route that has to
act on a form submission rather than render a page.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect

from apps.cms.models import DartIndexPage, DartPage


def find_dart(request: HttpRequest) -> HttpResponseRedirect:
    """Send the reader to the DART they chose in the home page's team finder.

    Reads the DART's primary key from the ``dart`` query parameter and redirects
    to the live page for that team.  A missing, unparsable, or unknown value, and a
    team with no published page, all fall back to the DART directory, and to the
    site root when no directory is published.  The redirect is always to a page on
    this site, so the parameter cannot steer the reader elsewhere.
    """
    raw = request.GET.get("dart", "")
    page: DartPage | None = None
    if raw.isdigit():
        page = DartPage.objects.live().public().filter(dart_id=int(raw)).first()
    if page is not None:
        return redirect(page.url)

    index_page = DartIndexPage.objects.live().first()
    return redirect(index_page.url if index_page is not None else "/")
