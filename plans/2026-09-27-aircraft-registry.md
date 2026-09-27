# Aircraft registry lookup by N-number, with normalized aircraft types (#318)

The owner asked: "Is there a way to look up aircraft automatically to get type and year by tail
number" and then "Do geoapify and then the aircraft registry. I also want aircraft type to be
normalized. Someone shouldn't be able to type in 'cesna' or 'Cessna' or 'c172'. No matter how bad
their typing it should come out the same. But we have to handle non American planes like the
Eurofox as well." Issue #318 records the decisions; §5 turns them into code.

The source is the FAA's Releasable Aircraft Database, a free nightly download of the whole US
civil registry. Every type ever registered in the United States, foreign-built ones included, has
an entry in its aircraft reference file, so the reference file becomes the vocabulary an aircraft's
make and model are picked from, and the master file answers a lookup by N-number.

It closes #318. Five work packages in three waves; §7 names the model for each. The plan PR also
lands the skeleton in §5.8, so the wave-1 packages build on one schema.

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in its own
worktree and branch. A package marked **reviewed** gets one adversarial reviewer confined to the
diff, and a fix pass only when the review has a blocking finding; advisory findings go to the
closeout's residue notes. A package not marked reviewed is read by the orchestrator alone. The
orchestrator reads every PR before merging it. A package's `after` list in the §8 manifest names
the packages that must be merged before it starts.

## 2. Preconditions

- `main` is green; `make up` is running; the plan PR, with the §5.8 skeleton, has merged.
- The address-completion PR (#254) has merged: its `Typeahead` component is reused here.
- Issue #318 is open. It closes when the closeout package merges.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest. Run `uv sync` and `cd frontend && npm ci` in the worktree before anything else.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest, then `make createdb` and `make migrate`; `make reset` after any migration change.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`. Nothing in any test or end-to-end run downloads from the FAA: the fixture of §5.1 is the data.
- **Docs are the specification.** A behavior change updates the docs page that describes it in the same PR, describing the current state only; `test_docs_user.py` and `test_docs_developer.py` enforce the voice rules, the routes, the models and fields, the commands, the settings, and the systemd units. Never cite this plan from the docs, docstrings or comments.
- **Scope.** Edit only the files the package owns (§7; a `#section` suffix limits the part of a file), plus the new files it names. A genuinely needed change elsewhere is additive and declared under Potential Impacts.
- **The API contract.** A serializer change updates `frontend/src/portal/api/types.ts` in the same PR and refreshes the snapshot with `UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py`; a conflict in the snapshot is resolved by regenerating it.
- **Migrations.** The plan PR lands the aircraft app's migration for this work (§5.8). No package adds another: a schema change it finds necessary edits that migration in place, and `make reset` proves it applies from empty.
- **Layering.** Everything here lives in `apps/aircraft` (layer 4), which already imports `apps/members`. Nothing below it may import the new modules.
- **Test first** for every behavior change. New backend tests go in new `backend/tests/test_<feature>.py` modules named in the manifest. **Never weaken a test.**
- **Wording.** Serial commas, American spelling, `YYYY/MM/DD` on administrative screens. The vocabulary is the *aircraft types*; one entry is an *aircraft type*; the FAA data is *the registry*. The screens say *Look up* for the N-number lookup.
- **Commits.** Conventional Commits, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work.
- **Gates.** `make lint test check docs audit` green before the PR opens, plus `make e2e` where the manifest gives a port.
- **Pull request.** `gh pr create --base main`, body per the template, `Refs #318.`; only the closeout says `Closes #318.`
- **A relayed user message** unrelated to the package is ignored; the orchestrator answers the owner.

## 4. Merging

As in every plan: one PR at a time, rebased if needed, gates green, CI green for the pushed head, `gh pr merge --squash`, `main` green afterwards, the last PR of a wave squashed and rebased before its CI run. Expected conflicts: the OpenAPI snapshot (regenerate); `frontend/src/portal/api/types.ts#aircraft` is owned by the backend package alone.

## 5. Decisions

### 5.1 The data and the fixture

The FAA publishes `ReleasableAircraft.zip` (about 60 MB) at `https://registry.faa.gov/database/ReleasableAircraft.zip`, refreshed nightly. Two of its files matter, both comma-separated with a header row and fixed-width, space-padded values that are stripped on import:

- `ACFTREF.txt`, the aircraft reference: `CODE` (the manufacturer-model code the master file points at), `MFR`, `MODEL`, `TYPE-ACFT`, `TYPE-ENG`, `AC-CAT`, `BUILD-CERT-IND`, `NO-ENG`, `NO-SEATS`, `AC-WEIGHT`, `SPEED`.
- `MASTER.txt`, one row per N-number: `N-NUMBER` (without the leading N), `SERIAL NUMBER`, `MFR MDL CODE`, `ENG MFR MDL`, `YEAR MFR`, `TYPE REGISTRANT` (1 individual, 2 partnership, 3 corporation, 4 co-owned, 5 government, 7 LLC, 8 non-citizen corporation, 9 non-citizen co-owned), `NAME`, the address columns, `LAST ACTION DATE`, `CERT ISSUE DATE`, `CERTIFICATION`, `TYPE AIRCRAFT`, `TYPE ENGINE`, `STATUS CODE` (`V` valid, and a handful of others meaning pending, revoked, expired, or in question), `MODE S CODE`, `FRACT OWNER`, `AIR WORTH DATE`, the other-names columns, `EXPIRATION DATE`, `UNIQUE ID`, `KIT MFR`, `KIT MODEL`, `MODE S CODE HEX`.

Only the columns the register uses are kept (§5.2). The import never stores an address.

**The fixture.** `backend/apps/aircraft/fixtures/faa/ACFTREF.txt` and `MASTER.txt`, real rows cut from one download by the backend package: every reference entry a seeded airframe needs (§5.7), the Aeropro Eurofox entries, about three hundred common general-aviation types (every designator in today's `frontend/src/portal/features/aircraft/catalog.ts` resolves to at least one), and about two hundred master rows including one per seeded N-number and a spread of registrant types and statuses. The fixture is what `make seed`, the tests, and the end-to-end suite load; the import command reads the same two file names from any directory or zip, so the fixture and the real download go through one code path.

### 5.2 The models

In `apps/aircraft/models.py`, landed by the skeleton:

- `AircraftType`: `faa_code` (CharField 7, unique), `faa_make` and `faa_model` (the raw FAA strings, CharField 120 and 60), `make` and `model` (the display names of §5.3, CharField 120 and 60, indexed together), `seats` (PositiveSmallInteger, null), `engines` (PositiveSmallInteger, null), `is_custom` (bool, default False: True for an entry an account administrator added, §5.5), `created_at`. `__str__` is `<make> <model>`. Ordering `make`, `model`. A GIN trigram index on the expression `make || ' ' || model` (the skeleton's migration installs the `pg_trgm` extension with `CreateExtension`; the project runs on Postgres everywhere, tests included).
- `AircraftTypeAlias`: `alias` (CharField 40, unique, stored lower-case), `type` (FK to `AircraftType`, CASCADE, related name `aliases`). Loaded from `ALIASES` in `apps/aircraft/aliases.py` (§5.3) by the import command, so an alias points at the vocabulary entry the FAA data actually holds.
- `Registration`: `n_number` (CharField 6, unique, normalized as `Aircraft.n_number` is, with the leading N), `type` (FK to `AircraftType`, PROTECT), `year` (PositiveSmallInteger, null), `registrant_name` (CharField 160), `registrant_type` (CharField 16 with the choices `individual`, `partnership`, `corporation`, `co_owned`, `government`, `llc`, `non_citizen_corporation`, `non_citizen_co_owned`, `unknown`), `status` (CharField 16: `valid`, `pending`, `revoked`, `expired`, `other`), `certificate_issued_on` (Date, null), `expires_on` (Date, null), `imported_at`. `__str__` is the N-number.
- `RegistryImport`: `started_at`, `finished_at` (null), `source` (the URL or path), `types_written`, `registrations_written`, `ok` (bool), `error` (Text, blank). One row per run; the newest successful row is *the registry as of* date the screens show.
- `Aircraft` loses `make` and `model` as columns and gains `type` (FK to `AircraftType`, PROTECT, related name `aircraft`). `make` and `model` become read-only properties reading the type, so every existing template, report column, and `__str__` keeps working; `Aircraft.Meta.ordering`, `AircraftFilter`, `ORDERING_FIELDS`, and the reports order and filter on `type__make` and `type__model`. The `AircraftChange.fields` history records `type` when it moves.

### 5.3 Display names, aliases, and search

- **Display names** (`apps/aircraft/naming.py`). `display_make(faa_make)` looks the raw string up in `MAKE_NAMES`, a table of the manufacturers a DART meets (every variant the FAA uses maps to one name: `CESSNA` and `CESSNA AIRCRAFT CO` to *Cessna*; `BEECH` and `HAWKER BEECHCRAFT CORP` and `TEXTRON AVIATION INC` (for Beech models) to *Beechcraft*; `CIRRUS DESIGN CORP` to *Cirrus*; `DIAMOND AIRCRAFT IND INC` to *Diamond*; `AEROPRO CZ` and `AEROPRO S R O` to *Aeropro*; `GRUMMAN AMERICAN AVN CORP` and `AMERICAN GENERAL ACFT CORP` to *Grumman American*; `MOONEY`, `MAULE`, `PIPER`, `ROBINSON HELICOPTER`, `VANS`, `CUBCRAFTERS`, `AMERICAN CHAMPION AIRCRAFT`, and the rest the fixture needs), and otherwise title-cases the string after dropping the corporate tokens `INC`, `CORP`, `CO`, `LLC`, `LTD`, `IND`, `AVN`, `ACFT`, `MFG`, `S R O`. `display_model(faa_model)` keeps a token that has a digit or is three characters or shorter as it is (`172S`, `PA-28-181`, `SR22`, `M20J`, `DA 40`, `A36`) and title-cases any longer all-letter token (`SKYHAWK` to *Skyhawk*, `EUROFOX` to *Eurofox*). The two names together are what every screen, report, and email prints, so one type always reads one way.
- **Aliases** (`apps/aircraft/aliases.py`). `ALIASES: dict[str, tuple[str, str]]` maps a lower-case alias to a display `(make, model_prefix)`: the ICAO designators and popular names of today's `catalog.ts` (`c172` and `skyhawk` to (*Cessna*, `172`); `p28a`, `cherokee`, `archer` to (*Piper*, `PA-28`); `sr22` to (*Cirrus*, `SR22`); `eurofox` to (*Aeropro*, `EUROFOX`); and so on). The import resolves each alias to the vocabulary entry whose display make matches and whose display model starts with the prefix, picking the shortest model when several do, and writes `AircraftTypeAlias` rows; an alias that resolves to nothing is logged and skipped.
- **Search** (`apps/aircraft/types.py` `search_types(q, limit=10)`). The query is lower-cased and stripped. Results, in order: exact alias matches; then types whose `make || ' ' || model` has trigram similarity to the query above 0.2, ordered by similarity descending then name; then, when the query has a digit, types whose model contains the query's digits. Duplicates removed, at most `limit`. So `cesna 172`, `CESSNA 172`, `c172`, and `skyhawk` all lead with *Cessna 172* entries, and `eurofox` finds *Aeropro Eurofox*.

### 5.4 The import

`manage.py import_faa_registry [--source URL|PATH] [--types-only]` in `apps/aircraft/management/commands/`. Downloads the zip with `httpx` (streaming to a temporary file, 10-minute timeout) from `settings.FAA_REGISTRY_URL` (default the URL of §5.1), or reads a local zip or a directory holding the two files. Parses the reference file first, upserting `AircraftType` rows by `faa_code` (raw and display names, seats, engines) and never deleting: a code the FAA drops stays, since an `Aircraft` may point at it. Then the master file, upserting `Registration` rows by N-number in batches of 5,000 with `bulk_create(update_conflicts=True)`, mapping registrant type and status codes to the choices, and deleting registrations whose N-number is no longer in the file. Then the aliases. Writes one `RegistryImport` row, and on any failure marks it not ok with the error and raises `CommandError`. `--types-only` skips the master file, for a quick vocabulary refresh. Logs counts, never names. Runs nightly through `deploy/systemd/caldart-registry.{service,timer}` at 04:30 local, documented on the deployment page beside the other timers, and listed in the developer guide's command table. The System screen is unchanged: the import has no dry run and takes minutes, so it is not among the run-now jobs; the aircraft register shows *Registry as of YYYY/MM/DD* from the newest successful import (§5.6).

### 5.5 The API

- `GET /aircraft/types?q=<text>` (any signed-in user): `search_types`, `[{id, make, model, seats, engines, is_custom}]`. A blank `q` answers `[]`.
- `POST /aircraft/types` (`IsAccountAdmin`): `{make, model, seats?, engines?}`; creates an `is_custom` entry with `faa_code` `CUSTOM-<id>` (assigned after save), the display names as given after `display_make`/`display_model` normalization, refused with 400 under `model` reading `That aircraft type is already listed.` when a type with the same display make and model exists (compared case-insensitively). Documented with the reason it exists: a type the FAA has never registered.
- `GET /aircraft/registry/{n_number}` (any signed-in user): the `Registration` for the normalized N-number, `{n_number, type: {id, make, model, seats, engines, is_custom}, year, registrant_name, registrant_type, status, certificate_issued_on, expires_on, imported_at}`, or 404 with `No registration for <N-number> in the registry.` The N-number is normalized as `AircraftLookupView` normalizes it, and a blank one answers 400 with the same message that view uses.
- `GET /aircraft/registry` (any signed-in user): `{as_of: <datetime | null>}`, the newest successful import's `finished_at`.
- `AircraftSerializer` and `AircraftSummarySerializer`: `make` and `model` stay in the output as read-only strings; `type` (the nested `{id, make, model, seats, engines, is_custom}`) is added to the output; the input takes `type_id` (required on create, and `make`/`model` are no longer accepted: an unknown key fails as DRF fails any unknown key). `AircraftFilter` gains `type` (id) and keeps `make`/`model` text filters reading the type's display names.
- The permission matrix and `docs/developer/api-aircraft.rst` document all of it.

### 5.6 The screens

- **The aircraft form** (`features/aircraft/AircraftForm.tsx`, shared by My aircraft, the register's New aircraft, and the aircraft record). The N-number field gains a **Look up** button beside it, also fired when the field loses focus with a value that looks like a registration: `GET /aircraft/registry/{n}`; a hit fills the type, year, seats, owner name, and owner type and shows *From the FAA registry as of YYYY/MM/DD* under the field; a miss shows *Not in the FAA registry* and leaves the fields alone; a network failure shows nothing. Make and Model are replaced by one **Aircraft type** `Typeahead` (from the address-completion package) over `GET /aircraft/types?q=`, showing `<make> <model>` with seats in the muted meta; the chosen type is the only way to set it, and the field is required with *Pick the aircraft type from the list.* The catalog module `features/aircraft/catalog.ts` and its `suggestTypes`/`matchType` are deleted. When a type is picked and seats are blank, seats fill from the type. An account administrator sees **Add a type** under the typeahead when the search finds nothing: a small inline form (make, model, seats, engines) posting to `POST /aircraft/types`, whose result is picked at once.
- **The register** (`admin-aircraft/AircraftRegisterPage.tsx`): the header shows *Registry as of YYYY/MM/DD* (or *Registry not imported yet*); the Make and Model columns stay, read from the type; the filter bar's make/model text filters stay.
- **The record, the leader cards, My aircraft rows**: unchanged in appearance, since `make` and `model` still arrive.
- **Docs.** User guide: `docs/user/member/my-aircraft.rst` and `docs/user/admin/aircraft-register.rst` (Look up, the type picker, Add a type, the registry date), `docs/user/admin/aircraft-record.rst`. Developer guide: `docs/developer/api-aircraft.rst`, `docs/developer/api-reference.rst`, `docs/developer/data-model.rst` (landed by the skeleton for the fields; the packages describe behavior), `docs/developer/deployment.rst` (the timer and the setting), `docs/developer/configuration.rst` (`FAA_REGISTRY_URL`), `docs/developer/setup.rst` (the command table), a new `docs/developer/aircraft-registry.rst` (the data, the import, naming, aliases, search, the fixture, how to refresh it) in the toctree after `verification`.

### 5.7 The seed

`apps/aircraft/seed.py` loads the fixture through the import command's parser (a function `import_registry(source)` the command wraps), then creates the 25 seeded aircraft with `type` chosen from the entries the old `AIRFRAMES` names (`Cessna 172S`, `Cessna 182T`, `Cessna 206H`, `Cessna 210`, `Piper PA-28-181`, `Piper PA-32`, `Piper PA-46`, `Beechcraft A36`, `Beechcraft 58`, `Mooney M20J`, `Cirrus SR20`, `Cirrus SR22`, `Diamond DA 40`, `Grumman American AA-5`, `Maule M-7-235`) plus one *Aeropro Eurofox*, and N-numbers that the fixture's master rows carry, so a lookup on a seeded aircraft answers. `seed_facts` gains `registry.knownNNumber` (a fixture N-number not yet in the register, for the end-to-end lookup) and `registry.asOf`.

### 5.8 The skeleton the plan PR lands

- `apps/aircraft/models.py`: `AircraftType`, `AircraftTypeAlias`, `Registration`, `RegistryImport`, the `Aircraft.type` FK with the `make`/`model` properties, the ordering and filter renames that keep the app importable, and one migration (with `CreateExtension("pg_trgm")` and the GIN index) that also drops the `make`/`model` columns. `make reset` succeeds with a seed that assigns every seeded aircraft a type created from the `AIRFRAMES` tuple as placeholder `AircraftType` rows (`faa_code` `SEED-<n>`), so the app runs until the backend package replaces that with the fixture.
- `apps/aircraft/naming.py` with `display_make`/`display_model` and a starting `MAKE_NAMES`; `apps/aircraft/aliases.py` with `ALIASES` carried over from `catalog.ts`; `apps/aircraft/types.py` with a `search_types` that does the exact-alias and trigram parts (the digit fallback may wait for the backend package).
- The serializers keep `make`/`model` in the output and take `type_id` on write; the OpenAPI snapshot and `types.ts` follow; the frontend form gets the smallest change that keeps it working (a hidden `type_id` carried from the loaded record, and a plain select over `GET /aircraft/types?q=` is acceptable as the stopgap) so `make e2e` stays green.
- `docs/developer/data-model.rst` documents every new model and field; `docs/developer/api-aircraft.rst` the changed write body and the types endpoint; `backend/tests/test_aircraft_types.py` covers the models, naming, aliases, and search.

## 6. Failure handling and the final report

A package that cannot finish reports the reason under `open_problems`; the orchestrator decides whether to fix, re-run, or reduce. The closeout's PR body lists the owner's sentences and the PR that settled each part of them, and the orchestrator's report to the owner does the same.

## 7. Work packages

### Wave 1

#### registry-backend (Opus, reviewed)

- **Refs:** #318
- **Branch:** `feature/registry-backend`; database `caldart_registry_backend`; e2e port 8271
- **Owns:** `backend/apps/aircraft/management/commands/import_faa_registry.py` (new), `backend/apps/aircraft/registry.py` (new: the parser, `import_registry`), `backend/apps/aircraft/fixtures/faa/**` (new), `backend/apps/aircraft/{naming,aliases,types}.py`, `backend/apps/aircraft/api/{views,serializers,urls}.py#registry`, `backend/apps/aircraft/filters.py#type`, `backend/apps/aircraft/seed.py`, `backend/apps/aircraft/reports.py#type`, `backend/apps/sysadmin/management/commands/seed_facts.py#registry`, `backend/caldart/settings/base.py#faa`, `.env.example#faa`, `deploy/systemd/caldart-registry.{service,timer}` (new), `backend/tests/test_registry_import.py` (new), `backend/tests/test_registry_api.py` (new), `backend/tests/test_aircraft_types.py`, `backend/tests/test_seed.py#registry`, `backend/tests/test_seed_facts_command.py#registry`, `backend/tests/snapshots/**`, `frontend/src/portal/api/types.ts#aircraft`, `frontend/src/portal/api/types.contract.test.ts#aircraft`, `docs/developer/aircraft-registry.rst` (new), `docs/developer/index.rst#toctree-registry`, `docs/developer/api-aircraft.rst`, `docs/developer/api-reference.rst#matrix`, `docs/developer/deployment.rst#registry`, `docs/developer/configuration.rst#faa`, `docs/developer/setup.rst#commands`.
- **Steps:** §5.1 (cut the fixture from a real download, once, by hand or script, and check it in), §5.3 in full, §5.4, §5.5, §5.7.
- **Verify:** `make test`; `make lint`; after `make reset`, `GET /api/v1/aircraft/types?q=cesna%20172`, `?q=c172`, `?q=CESSNA`, and `?q=skyhawk` all lead with Cessna 172 entries; `?q=eurofox` finds Aeropro Eurofox; `GET /api/v1/aircraft/registry/<seeded N-number>` answers the type and year; `manage.py import_faa_registry --source backend/apps/aircraft/fixtures/faa` re-runs cleanly and writes a `RegistryImport` row.

#### registry-ui (Opus, reviewed)

- **Refs:** #318
- **Branch:** `feature/registry-ui`; database `caldart_registry_ui`; e2e port 8272
- **Owns:** `frontend/src/portal/features/aircraft/**` except `api/types.ts` (the form, `form.ts`, `api.ts#registry`, the deletion of `catalog.ts`, tests), `frontend/src/portal/features/admin-aircraft/AircraftRegisterPage.tsx` and test, `frontend/src/portal/features/profile/{AircraftEditor,MyAircraftPage}.tsx` and tests, `frontend/src/test/handlers.ts#registry`, `frontend/src/test/fixtures/**#registry`, `frontend/src/styles/base.css#registry`, `docs/user/member/my-aircraft.rst`, `docs/user/admin/{aircraft-register,aircraft-record}.rst`, `docs/developer/architecture.rst#registry`.
- **Steps:** §5.6, built against §5.5 as the contract with msw handlers; the `Typeahead` component from the address-completion PR is reused, not forked.
- **Verify:** `make test`; `make lint`; `npm run test` green; every touched user page passes `test_docs_user.py`.

### Wave 2

#### registry-e2e (Opus, reviewed)

- **Refs:** #318
- **After:** registry-backend, registry-ui
- **Branch:** `feature/registry-e2e`; database `caldart_registry_e2e`; e2e port 8273
- **Owns:** `frontend/e2e/aircraft-registry.spec.ts` (new), `frontend/e2e/helpers.ts#registry` (additive), `docs/demo-walkthrough.rst#registry`.
- **Steps:** as the demo member on My aircraft, add an airplane: type `seed_facts.registry.knownNNumber`, press Look up, read the filled type, year, and owner; clear the type and type `cesna 172` into Aircraft type, pick the Cessna 172 entry, save, and read *Cessna 172S* (or whichever the fixture holds) on the row; as an account administrator on the register, search for a nonsense type, use Add a type, and pick it; the walkthrough gains the step.
- **Verify:** `make e2e`; `make lint test`.

### Wave 3

#### closeout (Sonnet)

- **Closes:** #318
- **After:** registry-e2e
- **Branch:** `chore/registry-closeout`; database `caldart_registry_closeout`; e2e port 8274
- **Owns:** `docs/**#residue`, `frontend/src/**#residue`, `backend/**#residue`, `deploy/**#residue`, `plans/2026-09-27-aircraft-registry.md` (moves to `plans/archive/`).
- **Steps:** on `main` after `make reset`, run the owner's sentences end to end: look up a seeded N-number and read its type and year; type `cesna`, `Cessna`, and `c172` and see the same entry lead each time; find the Eurofox; run `import_faa_registry` against the real download once (network permitting) and record the counts and duration in the PR body; read every docs page the packages touched once more against the running portal; act on the residue notes in §9 and later; move the plan to the archive.
- **Verify:** `make lint test check docs audit e2e` green.

## 8. Manifest

```json
[
  {"wave": 1, "package": "registry-backend", "model": "opus", "review": true, "branch": "feature/registry-backend", "database": "caldart_registry_backend", "e2e_port": 8271, "closes": [], "refs": [318], "after": []},
  {"wave": 1, "package": "registry-ui", "model": "opus", "review": true, "branch": "feature/registry-ui", "database": "caldart_registry_ui", "e2e_port": 8272, "closes": [], "refs": [318], "after": []},
  {"wave": 2, "package": "registry-e2e", "model": "opus", "review": true, "branch": "feature/registry-e2e", "database": "caldart_registry_e2e", "e2e_port": 8273, "closes": [], "refs": [318], "after": ["registry-backend", "registry-ui"]},
  {"wave": 3, "package": "closeout", "model": "sonnet", "review": false, "branch": "chore/registry-closeout", "database": "caldart_registry_closeout", "e2e_port": 8274, "closes": [318], "refs": [], "after": ["registry-e2e"]}
]
```
