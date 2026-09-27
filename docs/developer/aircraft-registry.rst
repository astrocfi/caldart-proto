=====================
The aircraft registry
=====================

Every aircraft on the register points at one **aircraft type**, a make and a
model picked from a fixed vocabulary rather than typed, so a Cessna 172 reads
the same way on every screen, report, and email whoever entered it and however
they spelled it.  The vocabulary, and the answer to a lookup by N-number, come
from **the registry**: the FAA's Releasable Aircraft Database, a free nightly
download of the whole US civil register.  Every type ever registered in the
United States has an entry in it, foreign-built ones such as the Aeropro Eurofox
included.

This page covers the data, the import that loads it, how an FAA name becomes a
display name, the aliases and the search built on them, the hand-added types,
and the fixture the demo data, the tests, and the end-to-end run load.  The
endpoints are in :doc:`api-aircraft` and :doc:`api-system`, the tables in
:doc:`data-model`, and the timer in :doc:`deployment`.


The data
========

The FAA publishes ``ReleasableAircraft.zip`` (about 70 MB) at
``https://registry.faa.gov/database/ReleasableAircraft.zip``, refreshed nightly.
Two of its files matter.  Both are comma-separated with a header row, written in
UTF-8 with a byte-order mark and Windows line endings, and every value is padded
with spaces to a fixed width; the import strips each value and each header name
as it reads them.

``ACFTREF.txt``, the aircraft reference, has one row per manufacturer-model code:

==================  =============================================================
Column              Becomes
==================  =============================================================
``CODE``            ``AircraftType.faa_code``, the seven-character code a
                    registration points at
``MFR``             ``faa_make``, and through ``display_make`` the ``make``
``MODEL``           ``faa_model``, and through ``display_model`` the ``model``
``NO-SEATS``        ``seats`` (``004`` is 4; blank is null)
``NO-ENG``          ``engines``
==================  =============================================================

``MASTER.txt`` has one row per N-number:

====================  ===========================================================
Column                Becomes
====================  ===========================================================
``N-NUMBER``          ``Registration.n_number``, which the FAA writes without the
                      leading ``N``; it is normalized as the register normalizes
                      one, so ``172SP`` is ``N172SP``
``MFR MDL CODE``      ``type``, the aircraft type with that ``faa_code``
``YEAR MFR``          ``year`` (blank is null)
``TYPE REGISTRANT``   ``registrant_type`` (below)
``NAME``              ``registrant_name``
``STATUS CODE``       ``status`` (below)
``CERT ISSUE DATE``   ``certificate_issued_on`` (``YYYYMMDD``; blank is null)
``EXPIRATION DATE``   ``expires_on``
====================  ===========================================================

The other columns — the registrant's address among them — are never read, so no
address is stored.

The registrant codes map to ``RegistrantType``: ``1`` individual, ``2``
partnership, ``3`` corporation, ``4`` co-owned, ``5`` government, ``7`` LLC,
``8`` non-citizen corporation, ``9`` non-citizen co-owned; a blank or any other
code is ``unknown``.

The FAA's status codes are many; they map to five ``RegistrationStatus`` values:

============  ===================================================================
Status        FAA codes
============  ===================================================================
``valid``     ``V`` (a valid registration), ``M`` (valid, under a
              manufacturer's dealer certificate), ``T`` (valid, from a trainee)
``pending``   ``R`` (registration pending), and the N-numbers assigned but not
              yet registered: ``2``, ``3``, ``4``, ``10``, ``11``, ``12``, ``19``
``revoked``   ``E``, ``W``, ``9``, ``21``, ``22``: revoked, or deemed ineffective
              or invalid
``expired``   ``D``, ``13``, ``16``, ``23``, ``27``, ``29``: the registration or
              the dealer certificate expired
``other``     everything else: a sale reported, a renewal notice outstanding, a
              reserved N-number, and the rest
============  ===================================================================

``REGISTRANT_TYPES`` and ``STATUSES`` in ``apps/aircraft/registry.py`` hold the
two tables.


The import
==========

``manage.py import_faa_registry`` runs it; the ``caldart-registry`` timer runs
the command daily at 04:30 (:ref:`deploy-registry`), and a system administrator
can start it from the System screen (below).

::

  uv run backend/manage.py import_faa_registry
  uv run backend/manage.py import_faa_registry --source /tmp/ReleasableAircraft.zip
  uv run backend/manage.py import_faa_registry --source backend/apps/aircraft/fixtures/faa
  uv run backend/manage.py import_faa_registry --types-only

``--source`` names what to read: an ``http`` or ``https`` URL of the zip, which
is streamed to a temporary file first (with a ten-minute timeout), or a local
zip or a directory holding the two files, as a path or a ``file://`` URL.
Without it the command reads ``FAA_REGISTRY_URL`` (:doc:`configuration`).  The
fixture and the real download go through the same code path.

``import_registry(source)`` in ``apps/aircraft/registry.py`` opens the source
first -- downloading it, when it names a URL, before anything else runs -- and
only then, in one transaction, does the work in this order:

1. **The aircraft types.**  Each reference row is upserted by ``faa_code``,
   refreshing the FAA names, the display names, seats, and engines.  A type is
   never deleted, even when the FAA drops its code: an aircraft may point at it.
2. **The fold** (below).
3. **The registrations.**  Unless ``--types-only`` is given, each master row is
   upserted by N-number, 5,000 at a time.  A row whose code the reference file
   does not hold is skipped and counted in the log.  Every registration the file
   no longer holds is then deleted, so an N-number the FAA has canceled drops
   out of the lookup.  ``--types-only`` leaves the registrations as they are, for
   a quick refresh of the vocabulary.
4. **The aliases** (below).

Every run writes one ``RegistryImport`` row: when it started and finished, the
source, the counts of types written, registrations written, and types folded,
and whether it succeeded.  A failure anywhere rolls the whole import back, so
the registry is never half-replaced; the row records it as not ``ok`` with the
error, and the command fails with a ``CommandError`` naming it.  The newest
successful row is the date the registry is *as of*, which the register's header
shows.  The log carries counts and never a registrant's name.

The whole registry — some 94,000 types and 317,000 registrations — imports in
well under a minute once the file is down.

Whichever way an import starts — the nightly timer or Run now — it takes the
same Postgres advisory lock and checks whether one is already running before
writing its ``RegistryImport`` row, so the two can never overlap.  Whichever
gets there first runs; the other fails the same way, with the timer's own
attempt reported through the command's ``CommandError`` rather than the 409
Run now answers.

Run now
-------

The System screen's *FAA registry import* row has a **Run now** button, which
calls ``POST /admin/system/registry-import`` (:ref:`api-registry-import`).
``start_import()`` writes the ``RegistryImport`` row, unfinished, and hands its
id to ``launch_import()``, which starts ``manage.py import_faa_registry
--import-id <id>`` in a process of its own and returns at once; the command
fills in the row it was given rather than creating one.  The screen polls
``GET /aircraft/registry`` until the import finishes.

While one import is running, a second press is refused.  An import that has not
finished within ``REGISTRY_IMPORT_STALE_MINUTES`` (30 by default) is taken to
have died — restarting the web service stops it — and the next press closes it
as failed, with the error *Did not finish.*, and starts another.  When the
subprocess itself cannot be started at all, the row is closed the same way at
once, with the error *Could not start the import.*, rather than sitting
unfinished until the stale timeout.  The launched process is a child of the web
service, not of the request: it is never waited on, so if it dies without
finishing its own row — a crash, or the service restarting under it — the row
is left exactly as an import that ran past the stale limit would leave it, and
the stale rule is what notices it.


Display names
=============

The FAA writes names in capitals and spells one manufacturer many ways
(``CESSNA``, ``CESSNA AIRCRAFT CO``, ``TEXTRON AVIATION INC``).
``apps/aircraft/naming.py`` turns each into the one name every screen prints.

``display_make(faa_make, faa_model)`` upper-cases the name, collapses its spaces,
and drops its full stops, then:

- a spelling of ``SHARED_MAKES`` is told apart by the model.  Textron Aviation
  holds both the Cessna and the Beechcraft type certificates and registers both
  under one name, so ``TEXTRON AVIATION INC`` is *Beechcraft* for a model
  starting ``B200``, ``B300``, ``C90``, ``G36``, ``G58``, ``F33``, ``AT6``,
  ``AT-6``, or ``3000``, and *Cessna* for any other;
- a spelling of ``MAKE_NAMES``, the table of manufacturers a DART meets, takes
  the name it lists: ``CESSNA AIRCRAFT CO`` is *Cessna*, ``BEECH`` and
  ``HAWKER BEECHCRAFT CORP`` are *Beechcraft*, ``AEROPRO CZ`` and
  ``AEROPRO CZ S R O`` are *Aeropro*, ``MOONEY AIRCRAFT CORP.`` is *Mooney*;
- any other loses a trailing ``S R O`` and the corporate words ``INC``,
  ``CORP``, ``CO``, ``LLC``, ``LTD``, ``IND``, ``AVN``, ``ACFT``, and ``MFG``,
  and each remaining word is title-cased: ``FOO AIRCRAFT CORP`` is
  *Foo Aircraft*.

``display_model(faa_model)`` keeps a word that holds a digit or is three
characters or shorter as the FAA writes it (``172S``, ``PA-28-181``, ``SR22``,
``DA 40``) and title-cases any longer word of letters (``SKYHAWK`` is
*Skyhawk*, ``EUROFOX`` is *Eurofox*).

Add a manufacturer to ``MAKE_NAMES`` when its FAA spellings would otherwise read
as two names, or as a corporate name nobody uses.


Aliases and search
==================

Nobody types ``172S`` when they mean a Skyhawk; they type ``c172`` or
``skyhawk``.  ``ALIASES`` in ``apps/aircraft/aliases.py`` maps each such name —
the ICAO designators and the popular names of the light aircraft a DART flies —
to a display make and the start of a display model: ``c172`` and ``skyhawk`` to
(*Cessna*, ``172``), ``p28a`` and ``archer`` to (*Piper*, ``PA-28``), ``eurofox``
to (*Aeropro*, ``Eurofox``).  At the end of every import ``write_aliases()``
points each alias at the type whose display make matches and whose display
model starts with the prefix, the shortest model when several do, and writes an
``AircraftTypeAlias`` row; an alias that names no type is logged and skipped.

``search_types(q)`` in ``apps/aircraft/types.py`` is the search behind
``GET /aircraft/types`` and the aircraft type picker.  The query is lower-cased
and stripped, and the answer lists, each type once and at most ten:

1. the type an alias names exactly, the alias compared as typed and with its
   spaces removed (``sr 22`` finds what ``sr22`` names);
2. the types whose ``make || ' ' || model``, or whose ``make`` alone, has a
   trigram similarity to the query above 0.2 (the ``pg_trgm`` extension, the
   greater of the two, over the GIN index the aircraft migration builds), most
   similar first; of equally similar types, the one more registrations name
   comes first, then by make and model.  Comparing the make alone as well as
   the full name is what lets a bare manufacturer name lead with that maker's
   most registered model: full-name similarity alone can favor a short,
   unrelated model over the popular one it should find, since the shorter
   string shares a larger fraction of its trigrams with the query;
3. when the query holds at least two digits, the types whose model contains
   them, run together as typed.  One digit is too little to narrow anything,
   so it never runs the fallback.

Two types with the same display make and model — the registry holds a few, one
``faa_code`` for an active production run and another for a superseded one —
collapse into the one with more registrations, so the picker never lists one
name twice; the type the search does not keep is still reachable through the
registration lookup, whose type comes from the registration's own ``faa_code``.

So ``cesna 172``, ``CESSNA 172``, ``c172``, and ``skyhawk`` all lead with the
Cessna 172, a bare ``cesna`` or ``piper`` leads with that maker's most
registered model, and ``eurofox`` finds the Aeropro Eurofox.


Hand-added types
================

A type the FAA has never registered — a homebuilt, or a foreign design no US
owner has registered yet — cannot be picked from the registry's vocabulary.  An
account administrator adds one from the type picker's **Add a type**, which
calls ``POST /aircraft/types`` (:doc:`api-aircraft`): the names are normalized
as the registry's are, the type is marked ``is_custom``, and its code is
``CUSTOM-<id>``.  A make and model already listed is refused, and so is a name
that normalizes to nothing — a corporate suffix alone, such as ``Inc.``, or bare
punctuation.

When the FAA later lists a type with the same display make and model, compared
case-insensitively, the next import **folds** the hand-added type into the FAA's
entry: every aircraft pointing at the hand-added type is re-pointed at the FAA's,
its aliases move with it, and it is deleted, so the vocabulary never holds two
spellings of one type.  The run's ``types_folded`` counts them.


The fixture
===========

``backend/apps/aircraft/fixtures/faa/`` holds an ``ACFTREF.txt`` and a
``MASTER.txt`` cut from one real download: 330 reference rows and 210 master
rows, byte for byte as the FAA wrote them except that the address columns
(street, city, state, ZIP code, region, county, and country) and the other-names
columns of the master rows are blanked to spaces of the same width.  ``make seed``
imports it (``apps/aircraft/seed.py``), and so do the tests and the end-to-end
run, whose server has ``FAA_REGISTRY_URL`` set to the fixture directory, so
**Run now** there imports the fixture.  Nothing in a test or an end-to-end run
downloads from the FAA.

The reference rows are:

- every type the seeded aircraft fly (``AIRFRAMES`` in
  ``apps/aircraft/seed.py``), with every other code of the same display name;
- every Aeropro entry, the Eurofox among them;
- for every alias, the entry it resolves to in the full registry, with every
  other code of the same display name, so every alias resolves against the
  fixture exactly as it does against the full download;
- and the most registered fixed-wing and rotorcraft types under 12,500 pounds
  to make up the rest.

The master rows are at least three valid registrations, each with a year, of every
seeded type (the seed takes its N-numbers from them); eight of the plain
Cessna 172, the most of any Cessna, so a bare ``cessna`` leads with it; three
of each registrant code and two of each of the commoner status codes; and valid
registrations of the fixture's types to make up the rest.

To refresh it, download the zip, unpack the two files, and cut them by the same
rules, keeping each kept row's line exactly as the FAA wrote it and blanking
the same columns.  Then run ``uv run pytest backend/tests/test_registry_import.py
backend/tests/test_aircraft_types.py backend/tests/test_seed.py``: the counts,
the aliases, and the seed's registrations are all checked against the fixture.
