"""Where a raised event becomes the emails the subscribed addresses receive."""

from __future__ import annotations

from collections.abc import Mapping


def handle(slug: str, payload: Mapping[str, object]) -> None:
    """Receive the event ``slug`` with ``payload`` and send it to its subscribers.

    Nothing is sent yet: the catalog is declared, the subscriptions and the sending
    follow.
    """
