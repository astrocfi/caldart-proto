"""The aircraft type search behind the type picker and ``GET /aircraft/types``.

However a type is typed -- ``cesna 172``, ``CESSNA``, ``c172``, ``skyhawk`` -- the
search should lead with the same entry.  It looks three ways, in order: an exact alias
(``AircraftTypeAlias``), then trigram similarity to the display name, then, when the
query holds digits, the models that contain them.  Where the display names resemble
the query equally, the type more aircraft are registered as comes first, so a bare
manufacturer name leads with that maker's most common type.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Count

from apps.aircraft.models import AircraftType, type_name_expression

#: How many types a search answers unless told otherwise.
DEFAULT_LIMIT = 10

#: The trigram similarity a display name needs to the query to be answered.
SIMILARITY_THRESHOLD = 0.2


def search_types(q: str, limit: int = DEFAULT_LIMIT) -> list[AircraftType]:
    """The aircraft types matching ``q``, best first, at most ``limit`` of them.

    ``q`` is lower-cased, stripped, and its runs of spaces collapsed; a blank query
    answers ``[]``.  The answer lists, in order and each type once:

    1. the type an alias names exactly, the alias compared as typed and with its spaces
       removed (so ``sr 22`` finds what ``sr22`` names);
    2. the types whose ``make || ' ' || model`` has a trigram similarity to the query
       above :data:`SIMILARITY_THRESHOLD`, most similar first, then the one with more
       registrations in the registry, then by make and model;
    3. when the query holds digits, the types whose model contains those digits, run
       together as typed (``c172`` finds models containing ``172``), by make and model.
    """
    term = " ".join(q.lower().split())
    if not term:
        return []
    found: dict[int, AircraftType] = {}

    def take(rows: Iterable[AircraftType]) -> None:
        """Add each of ``rows`` not already found, until ``limit`` types are found."""
        for row in rows:
            if len(found) >= limit:
                return
            found.setdefault(row.pk, row)

    aliases = {term, term.replace(" ", "")}
    take(AircraftType.objects.filter(aliases__alias__in=aliases).order_by("make", "model")[:limit])
    take(
        AircraftType.objects.annotate(
            similarity=TrigramSimilarity(type_name_expression(), term),
            registered=Count("registrations"),
        )
        .filter(similarity__gt=SIMILARITY_THRESHOLD)
        .order_by("-similarity", "-registered", "make", "model")[:limit]
    )
    digits = "".join(character for character in term if character.isdigit())
    if digits:
        take(AircraftType.objects.filter(model__contains=digits).order_by("make", "model")[:limit])
    return list(found.values())
