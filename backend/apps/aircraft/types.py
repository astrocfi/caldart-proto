"""The aircraft type search behind the type picker and ``GET /aircraft/types``.

However a type is typed -- ``cesna 172``, ``CESSNA``, ``c172``, ``skyhawk`` -- the
search should lead with the same entry.  It looks three ways, in order: an exact alias
(``AircraftTypeAlias``), then trigram similarity to the display name or to the make
alone, then, when the query holds at least two digits, the models that contain them.
Where the display names resemble the query equally, the type more aircraft are
registered as comes first, so a bare manufacturer name leads with that maker's most
common type; two entries that display identically collapse into the more registered
one, so the list never repeats a name.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Count
from django.db.models.functions import Greatest

from apps.aircraft.models import AircraftType, type_name_expression

#: How many types a search answers unless told otherwise.
DEFAULT_LIMIT = 10

#: How many candidates are gathered, before duplicate display names are collapsed,
#: for every type of the search the query holds enough spare room to still answer
#: ``limit`` distinct names.  The FAA data holds a handful of duplicates in a row
#: (several codes sharing one display make and model), never dozens.
_CANDIDATE_POOL_FACTOR = 5

#: The trigram similarity a display name, or a make alone, needs to the query to be
#: answered.
SIMILARITY_THRESHOLD = 0.2

#: How many digits a query needs before the digit fallback runs.  A single digit
#: matches too much of the vocabulary to be useful (see the module docstring); two
#: or more, as in ``c172`` or ``sr22``, narrows it to a handful of models.
MIN_DIGIT_LENGTH = 2


def search_types(q: str, limit: int = DEFAULT_LIMIT) -> list[AircraftType]:
    """The aircraft types matching ``q``, best first, at most ``limit`` of them.

    ``q`` is lower-cased, stripped, and its runs of spaces collapsed; a blank query
    answers ``[]``.  Candidates are gathered, each type once, in this order:

    1. the type an alias names exactly, the alias compared as typed and with its spaces
       removed (so ``sr 22`` finds what ``sr22`` names);
    2. the types whose ``make || ' ' || model``, or whose ``make`` alone, has a trigram
       similarity to the query above :data:`SIMILARITY_THRESHOLD` -- the greater of the
       two -- most similar first, then the one with more registrations in the registry,
       then by make and model.  Comparing the make alone as well as the full name is
       what lets a bare manufacturer name (``cesna``, ``piper``) lead with that maker's
       most registered model rather than whichever model's full name happens to
       resemble the query more by chance;
    3. when the query holds at least :data:`MIN_DIGIT_LENGTH` digits, the types whose
       model contains those digits, run together as typed (``c172`` finds models
       containing ``172``), by make and model.

    Two candidates with the same display make and model -- the registry holds a few,
    one ``faa_code`` for an active production run and another for a superseded one --
    collapse into the one with more registrations before the list is cut to ``limit``.
    """
    term = " ".join(q.lower().split())
    if not term:
        return []
    pool = limit * _CANDIDATE_POOL_FACTOR
    found: dict[int, AircraftType] = {}

    def take(rows: Iterable[AircraftType]) -> None:
        """Add each of ``rows`` not already found, until the candidate pool is full."""
        for row in rows:
            if len(found) >= pool:
                return
            found.setdefault(row.pk, row)

    aliases = {term, term.replace(" ", "")}
    take(AircraftType.objects.filter(aliases__alias__in=aliases).order_by("make", "model")[:pool])
    take(
        AircraftType.objects.annotate(
            similarity=Greatest(
                TrigramSimilarity(type_name_expression(), term),
                TrigramSimilarity("make", term),
            ),
            registered=Count("registrations"),
        )
        .filter(similarity__gt=SIMILARITY_THRESHOLD)
        .order_by("-similarity", "-registered", "make", "model")[:pool]
    )
    digits = "".join(character for character in term if character.isdigit())
    if len(digits) >= MIN_DIGIT_LENGTH:
        take(AircraftType.objects.filter(model__contains=digits).order_by("make", "model")[:pool])
    return _collapse_duplicates(found.values())[:limit]


def _collapse_duplicates(candidates: Iterable[AircraftType]) -> list[AircraftType]:
    """``candidates``, one entry per display make and model, the more registered kept.

    Keeps the relative order candidates were found in: the first type found for a
    display name holds that position, even when a later duplicate turns out to be the
    one kept.  A type dropped here is still reachable through the registration lookup,
    whose type comes from the registration's own ``faa_code``, not from this search.
    """
    ordered = list(candidates)
    registered = dict(
        AircraftType.objects.filter(pk__in=[entry.pk for entry in ordered])
        .annotate(registered=Count("registrations"))
        .values_list("pk", "registered")
    )
    kept: dict[tuple[str, str], AircraftType] = {}
    order: list[tuple[str, str]] = []
    for entry in ordered:
        key = (entry.make, entry.model)
        if key not in kept:
            order.append(key)
            kept[key] = entry
        elif registered[entry.pk] > registered[kept[key].pk]:
            kept[key] = entry
    return [kept[key] for key in order]
