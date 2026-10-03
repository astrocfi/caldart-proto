"""Where an email log row leads in the portal, for a message that belongs to a record.

Most messages stand alone, but some belong to a record of the app that sent them: each
copy of a bulk email belongs to that bulk email.  The Sent Emails page links such a row
to its record.  The mail app sits below the apps that send through it and never imports
them, so an app whose messages belong to a record registers a source of links with
:func:`register_log_links` from its ``AppConfig.ready()``, as the bulk email app does,
and :func:`log_links` asks every source about a page of rows at once.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Read only by the checker: an app's ``ready()`` imports this module before the
    # models may be imported.
    from apps.mail.models import EmailLog

#: A function answering, for the rows given, the portal path of each row it knows, by
#: the row's id.  A path is relative to the portal, such as ``/bulk-email/sent/9``.
type LinkSource = Callable[[Sequence[EmailLog]], dict[int, str]]

#: The registered sources, in the order :func:`log_links` asks them.
_link_sources: list[LinkSource] = []


def register_log_links(source: LinkSource) -> None:
    """Add ``source`` to the functions :func:`log_links` asks.

    Registering the same source twice registers it once.
    """
    if source not in _link_sources:
        _link_sources.append(source)


def log_links(rows: Sequence[EmailLog]) -> dict[int, str]:
    """The portal path each of ``rows`` leads to, by row id; a row with none is absent.

    Every registered source is asked once about all of ``rows``, in registration order,
    and a later source's answer for a row wins.  A source may read the database, so a
    caller listing a page of rows asks once for the whole page.
    """
    links: dict[int, str] = {}
    for source in _link_sources:
        links.update(source(rows))
    return links
