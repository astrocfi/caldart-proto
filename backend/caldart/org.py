"""Who CalDART is, on paper.

The organization's name, the address members write to, where mail is sent, the
EIN a 501(c)(3) receipt has to carry, and the site every email links into.  They
live on Wagtail's ``SiteSettings``, which a website administrator edits, and one
function gathers them so a receipt, a statement or an email never reads the CMS
itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    # Inline: for typing only.  A real import would make this module, which the
    # lower layers read, depend on cms, the top one.
    from apps.cms.models import SiteSettings

#: The name used before a website administrator has filled the settings in.
DEFAULT_ORG_NAME = "CalDART"


@dataclass(frozen=True)
class OrgDetails:
    """The organization's letterhead, as a receipt or an email prints it.

    ``name`` is never empty: it falls back to ``CalDART``.  ``contact_email``,
    ``mailing_address`` and ``ein`` are empty strings when nobody has entered
    them, and whatever prints them leaves the line out rather than printing a
    blank one.  ``site_url`` carries no trailing slash, so a link is built by
    appending a rooted path to it.
    """

    name: str
    contact_email: str
    mailing_address: str
    ein: str
    site_url: str


def site_settings() -> SiteSettings | None:
    """The default site's ``SiteSettings`` row, or ``None`` when there is none.

    It is ``None`` before ``migrate`` has set the site up, and reading it never
    creates the row.
    """
    # Inline: the site settings live in cms, the top layer, and a top-level
    # import would make every caller of this module depend upward on it.
    from apps.cms.models import get_site_settings

    return get_site_settings()


def org_details() -> OrgDetails:
    """Gather the organization's letterhead from the site settings.

    Reads the default site's row once.  A missing row, or a blank field in it,
    gives the fallbacks described on :class:`OrgDetails`; nothing raises, so a
    receipt still renders on a site nobody has configured yet.
    """
    row = site_settings()
    return OrgDetails(
        name=(row.org_name if row else "") or DEFAULT_ORG_NAME,
        contact_email=(row.contact_email if row else "") or "",
        mailing_address=(row.mailing_address if row else "") or "",
        ein=(row.ein if row else "") or "",
        site_url=settings.SITE_URL.rstrip("/"),
    )
