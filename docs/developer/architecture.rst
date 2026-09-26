============
Architecture
============

How CalDART fits together: the two things it serves, the stack underneath,
where each responsibility lives, and the path a request takes from the
browser to the code that answers it.  The detail is in the pages this one
links to.


Overview
========

CalDART is the website and member management system for |org|, a 501(c)(3)
that organizes California pilots and ground personnel to provide volunteer
disaster air transportation.  Members belong to DARTs (Disaster Airlift
Response Teams): local teams, each based at an airport.

One Django project serves two deliverables from one origin:

**The public website**
    Server-rendered Wagtail pages: home, history and officers, the DART
    directory, news, joining and donating, sponsors, contact, and a
    members-only area.  Website administrators edit it in the Wagtail admin
    at ``/admin/``.

**The member portal**
    A React single-page application (SPA) under ``/portal/``, backed by a
    JSON API under ``/api/v1/``.  Members join, pay, renew, and keep their
    profiles and aircraft up to date; DART leaders check whether a member may
    fly a mission; administrators look after accounts, members, aircraft
    , payments, and the server.

Editors get Wagtail's page tree, previews, and revision history, and the
public pages work without JavaScript; the member flows get a real
application.  Both halves share one design system and one theme setting
(:doc:`theming`).

Five flows shape the system, and each has to be quick on a phone.  The
:doc:`/demo-walkthrough` drives them by hand on the demo data, and the
Playwright suite drives them in a browser (:doc:`testing`):

- :ref:`walkthrough-flow-a`
- :ref:`walkthrough-flow-b`
- :ref:`walkthrough-flow-c`
- :ref:`walkthrough-flow-d`
- :ref:`walkthrough-flow-e`

What the prototype leaves out on purpose is in :doc:`roadmap`.


Stack
=====

Major versions only; ``uv.lock`` and ``frontend/package-lock.json`` pin the
exact ones.

==============  ==============================================================
Layer           What CalDART uses
==============  ==============================================================
Backend         Python 3.12, Django 6, and Django REST Framework 3 with
                django-filter; django-environ reads settings from the
                environment or ``.env``; django-csp sends the
                Content-Security-Policy header (:ref:`configuration-csp`)
CMS             Wagtail 8: page tree, StreamField, images, documents, site
                settings
Database        PostgreSQL 16 in Docker Compose, through psycopg 3
Portal          TypeScript 5 in strict mode, React 19, React Router 7 and
                TanStack Query 5
Assets          Vite 6 builds them; django-vite writes the bundles, or the
                Vite dev server, into templates; WhiteNoise serves
                ``/static/``
Payments        Stripe: the ``stripe`` library on the server, Stripe.js, and
                the Payment Element in the browser (card, Apple Pay, Google
                Pay, Link).  PayPal: the Orders v2 REST API through httpx,
                with no SDK, and ``@paypal/react-paypal-js`` in the browser.
                A mock provider for development and tests
Reports, email  reportlab for PDF and the standard library's ``csv`` for CSV;
                Django's email framework, with Mailpit in development (SMTP
                on port 1025, web interface on 8025)
Operations      gunicorn behind Apache 2.4 or nginx; a management command
                run daily by a systemd timer
Tooling         uv and npm; ruff and mypy; tsc, ESLint 9 and Prettier; pytest,
                pytest-django, factory_boy, freezegun, and respx; Vitest,
                Testing Library and msw; Playwright; Sphinx with furo; GitHub
                Actions, where every step is a make target
==============  ==============================================================


Repository layout
=================

::

  caldart-proto/
    README.rst                  quick start
    CLAUDE.md                   working conventions for coding agents
    Makefile                    every task; `make help` lists the everyday ones
    docker-compose.yml          Postgres and Mailpit, project name "caldart"
    .env.example                every environment variable, with dev defaults
    pyproject.toml, uv.lock     backend dependencies; ruff, mypy, pytest settings
    .github/workflows/ci.yml    the CI pipeline
    .claude/
      rules/                    coding, testing, and documentation standards
      skills/                   repeatable workflows (docs, critiques, PRs)
    backend/
      caldart/                  the Django project
        settings/               _dotenv.py (the .env read), base.py,
                                dev.py (the default), prod.py, test.py
        urls.py                 the root URLconf
        api_urls.py             /api/v1/: includes every app's api/urls.py
        views.py                portal_shell, the page the SPA runs in, and
                                user_guide, the built guide behind the login
        authentication.py       session auth, with CSRF for anonymous callers
        models.py               TimestampedModel, the abstract base every
                                model inherits
        pagination.py           page-number pagination for the API
        exceptions.py           DRF error handling (401 for anonymous)
        reports.py              the report engine: specs, columns, and the
                                CSV and PDF every report is built as
        audit.py                the audit log: one record per privileged
                                action, ids, and slugs only
      apps/                     one Django app per domain area
        accounts/  darts/  mail/  members/  aircraft/
        payments/  reminders/  reports/  cms/  sysadmin/
      templates/
        base.html               the public-site shell
        portal.html             the SPA mount point
        cms/                    page, block, and include templates
        emails/                 password, invitation, and reminder mail
      tests/                    every backend test, one test_<feature>.py each
      media/                    Wagtail uploads (gitignored)
      staticfiles/              collectstatic output (gitignored)
    frontend/
      vite.config.ts            three entry points: site, donate, and portal
      src/
        styles/                 tokens, base, and site styles, themes/
        site/                   public-site enhancements and the donate mount
        donate/                 the public donation form
        portal/                 the member portal SPA
        test/                   msw server, default handlers, render helpers
      e2e/                      Playwright specs, one per flow
      dist/                     Vite build output (gitignored)
    deploy/
      caldart.env.example       the production environment template
      gunicorn.conf.py
      systemd/                  caldart-web.service, caldart-reminders.*
      apache/caldart.conf       the reverse proxy
      nginx/caldart.conf        the nginx alternative
    docs/                       this documentation: user/ and developer/
    plans/                      implementation plans for work in progress
      archive/                  finished plans, kept as a record
    critiques/                  dated review reports on the code and docs
    backups/                    database dumps (gitignored)

Frontend tests sit beside the file they test (:doc:`testing`).


How a request is served
=======================

In production Apache (or nginx) terminates TLS, serves uploads under
``/media/`` from disk — except ``/media/documents/``, which it refuses so that
Wagtail's document view can apply the members-only guard (:doc:`cms`) — and
proxies everything else to gunicorn on
``127.0.0.1:8001`` (:doc:`deployment`); in development ``make run`` serves
the same URLs on port 8000.  Inside Django, WhiteNoise answers ``/static/``
from the middleware stack, and everything else goes through
``caldart/urls.py``, in this order:

====================  ========================================================
Path                  Served by
====================  ========================================================
``/admin/``           the Wagtail admin
``/django-admin/``    Django's model admin, for the accounts, darts,
                      members, aircraft, payments, reminders, mail, and
                      reports models
``/documents/``       Wagtail's document downloads
``/api/v1/``          the JSON API
``/.well-known/``     only ``apple-developer-merchantid-domain-association``,
                      the Apple Pay domain-verification file
``/find-dart/``       ``apps.cms.views.find_dart``: the home page's DART
                      finder, which redirects ``?dart=<id>`` to that team's
                      live page, or to the DART directory (the site root
                      when none is published) for a missing or unknown team
``/docs/<path>``      ``caldart.views.user_guide``: the built user guide,
                      served to signed-in users from ``USER_GUIDE_ROOT``
``/portal/<path>``    ``caldart.views.portal_shell``, the page the SPA runs in
``/media/``           uploaded files, while ``DEBUG`` is on
anything else         Wagtail's page serving: a catch-all, so it stays last
====================  ========================================================

**Public pages.**  Wagtail matches the path against its page tree and
renders the page's template, which extends ``templates/base.html``; the
``site_chrome`` context processor supplies the site settings, theme, and
navigation.  A page flagged ``members_only`` renders the members-only wall
with HTTP 403 instead, unless the visitor's ``can_access_members_content``
is true (:doc:`cms`).

**The portal shell.**  Every URL under ``/portal/`` returns the same HTML:
``portal_shell`` renders ``portal.html``, which sets ``<html data-theme>``
from the site's theme and loads the portal bundle.  The server knows nothing
of the SPA's routes and makes no access decision here; React Router picks
the screen in the browser, so a reload or a shared link lands in the right
place.  Django's ``LOGIN_URL`` is ``/portal/login``.

**The user guide.**  ``make guide`` builds ``docs/user/`` alone into
``docs/_build/guide``, and ``user_guide`` serves those files at ``/docs/`` to
anyone signed in; a visitor who is not is sent to the portal's login page with
the guide page as ``next``, and the login page hands them back to the guide
with a full-page navigation, since the guide lives outside the SPA.  The
portal's top bar carries a **Help** link, shown whether or not anyone is
signed in, that opens the guide page for the screen the visitor is on:
``help.ts`` maps every route pattern to a guide slug in ``HELP_PAGES``, in
match order, and ``helpPath`` returns the first match's page, or the guide's
front page for a route with none.  The rail's **User guide** link and the
public site's footer link both open that front page.  The developer guide is
not published, and no user page links into it (:doc:`documentation`).

**The API.**  ``caldart/api_urls.py`` includes every app's ``api/urls.py``
under ``/api/v1/``, and each app spells out its own paths, so adding an
endpoint touches no shared file.  The DRF defaults in ``settings/base.py``
hold unless a view says otherwise: session authentication only;
``IsAuthenticated``, so a public endpoint opts out explicitly; JSON only;
``?page=`` and ``?page_size=`` pagination; django-filter, ``?search=`` and
``?ordering=``; and an exception handler that answers an anonymous request
with 401 rather than 403.  Role checks use the classes in
``apps/accounts/permissions.py``, which ``system_admin`` always passes, and
sign-in, registration, and password reset are rate-limited
(:doc:`api-reference`).

**Sessions and CSRF.**  The portal shares the API's origin, so it signs in
with Django's session cookie and stores no token: ``POST /api/v1/auth/login``
starts a session, and ``GET /api/v1/auth/me`` says who is signed in (401 for
nobody).  Before any unsafe request, the API client calls
``GET /api/v1/auth/csrf`` if it has no ``csrftoken`` cookie, then echoes that
cookie in ``X-CSRFToken`` on every ``POST``, ``PUT``, ``PATCH``, and
``DELETE``.  The cookie is the cache, so a bootstrap that fails is simply
tried again by the next write rather than leaving the page unable to save.
That is why production keeps the CSRF cookie readable from JavaScript while
the session cookie is HttpOnly (:doc:`configuration`).

**Static files.**  Vite builds three entry points, ``src/site/main.ts``,
``src/site/donate.tsx``, and ``src/portal/main.tsx``, into ``frontend/dist/`` with
hashed names under
``/static/`` and a manifest at ``frontend/dist/.vite/manifest.json``, from
which ``{% vite_asset %}`` writes a template's tags.  ``frontend/dist/`` is
on ``STATICFILES_DIRS``, so after ``make build`` the development server
serves it.  With ``DJANGO_VITE_DEV_MODE=true`` and ``make dev-frontend``
running, the tags point at the Vite dev server on ``localhost:5173``
instead, with hot module replacement.  In production ``collectstatic``
copies the build into ``backend/staticfiles/`` for WhiteNoise, and Apache
and nginx proxy ``/static/`` through rather than aliasing it, so the
manifest stays authoritative.


The backend apps
================

Ten apps under ``backend/apps/``, one per domain area.  The usual files
are ``models.py``, ``services.py``, ``filters.py``, an ``api/`` package
(``urls.py``, ``views.py``, ``serializers.py``), ``admin.py``,
``reports.py``, ``seed.py``, ``management/commands/``, and ``migrations/``;
not every app needs every one.  A list whose filters a report reuses keeps its
filter set in the app's own ``filters.py`` rather than under ``api/``, so the
report, a domain module, can read it.

``accounts``
    The custom ``User``, whose login is the email address; the seven roles,
    stored as Django ``Group`` rows (``roles.py``); the permission classes
    (``permissions.py``); and the auth rate limits (``throttling.py``).
    Endpoints ``/auth/...``, ``/admin/users`` and ``/roles``; commands
    ``seed_roles`` and ``seed_demo``.
``darts``
    ``Dart`` and ``DartContact``: the teams, the airports each flies from, the
    team's own website and the people who run it.  Endpoints: the public
    ``/darts`` catalog and the account administrator's ``/admin/darts``.  The
    app sits below ``members``, because a profile names a DART and a DART
    knows nothing about any member.
``mail``
    ``EmailLog``: one row per email the installation tried to send, written by
    ``caldart.mail.send_templated`` after every send, successful or refused.
    Endpoint ``GET /system/emails``.  The app holds no sender of its own, so it
    sits below everything that mails anybody.
``members``
    ``MemberProfile``, ``MembershipPlan``, and ``Membership``, and the rules
    for whether a membership is current.  Endpoints: the member's own
    ``/me/...``, the public ``/plans``, and the account administrator's
    ``/admin/members`` and ``/admin/memberships``.  ``reports.py`` declares the
    membership report.
``aircraft``
    ``Aircraft``, the shared register with insurance data.  Endpoints
    ``/aircraft...`` and the DART leader check under ``/leader/``;
    ``reports.py`` declares the aircraft report.
``payments``
    ``Payment``, ``Refund``, ``RenewalMandate`` and ``RenewalAttempt``; the
    provider plugins in ``providers/`` (``stripe``, ``paypal``, and
    ``mock``); checkout, confirmation, webhooks, receipts, refunds, payment
    reporting, reconciliation, and automatic renewal.  Endpoints
    ``/payments/...``, ``/me/payments/...``, ``/me/renewal``, ``/me/donation``, the finance
    area's ``/admin/payments...`` and ``/admin/renewals...``, and
    ``/system/renewals/run``; ``views.py`` also serves the Apple Pay
    domain-verification file.  ``reports.py`` declares the payments and
    contributions reports, and ``reconciliation.py`` the reconciliation
    report.
``reminders``
    ``ReminderLog`` and the renewal-reminder scanner, with its
    ``send_renewal_reminders`` command.  Endpoints ``/admin/reminders/log``
    and ``/system/reminders/run``.
``reports``
    Everything that spans the reports: the registry of every app's report
    (``registry.py``), who may read one (``permissions.py``), and the
    endpoints under ``/reports/`` that list them, answer their columns and
    download them (:doc:`api-reports`).  It keeps each account's
    ``SavedColumnSet`` and the ``ReportSubscription`` rows, and sends the
    subscriptions and each DART's roster by email with its
    ``send_scheduled_reports`` command (:doc:`scheduled-reports`); endpoint
    ``/system/reports/run``.  It gathers reports from the apps below it, so it
    sits beside ``reminders``.
``cms``
    The Wagtail page types, the StreamField blocks, ``SiteSettings``, the
    members-only wall, the ``site_chrome`` context processor and the
    ``website_admin`` editor permissions.  Endpoint ``/site/config``; command
    ``seed_content``.
``sysadmin``
    No models: backup, restore, reset, and health, as the commands
    ``db_backup``, ``db_restore``, ``db_reset``, and ``health``, and the
    endpoints ``/system/health`` and ``/system/backups``.

Code that several apps share lives in the project package:
``caldart/models.py`` (``TimestampedModel``, the abstract base that gives every
model ``created_at`` and ``updated_at``), ``caldart/reports.py`` (the report
engine: ``ReportSpec``, the column registry, and ``build_report``, which turns
any report into a CSV or a PDF in the house style), ``caldart/receipts.py`` (the
receipt and contribution-statement PDFs, both described in :doc:`reports`),
``caldart/mail.py`` (one templated-email sender, which also writes the email
log), ``caldart/org.py`` (the
organization's letterhead, read from the Wagtail site settings),
``caldart/audit.py`` (the audit log, described in :ref:`deploy-audit-log`),
``caldart/pagination.py`` and ``caldart/exceptions.py``.
``make seed`` runs ``seed_roles``, then ``seed_demo`` (every app's ``seed.py``,
with a fixed random seed so every machine gets the same data), then
``seed_content``; all three are idempotent.

.. _architecture-app-dependencies:

Dependencies between apps
-------------------------

The apps depend on each other in one direction only, so a change is read in one
place rather than three.  The rule applies to every *domain* module -- anything
outside ``api/``, ``admin.py``, and ``management/``: ``models.py``,
``services.py``, ``reports.py``, ``roles.py``, ``permissions.py``, ``seed.py``,
and the rest.  A domain module imports its own app or an app on a lower layer,
never one on the same layer or a higher one:

==========================================  ==================================
Layer                                       Apps
==========================================  ==================================
0, the foundation                           ``caldart.models``,
                                            ``caldart.reports``,
                                            ``caldart.exceptions``, and
                                            ``caldart.pagination``, which
                                            import no app at all
1                                           ``accounts``
2                                           ``darts`` and ``mail``, siblings
                                            that never import each other
3                                           ``members``
4                                           ``aircraft`` and ``payments``,
                                            siblings that never import each
                                            other
5                                           ``reminders`` and ``reports``,
                                            siblings that never import each
                                            other
6                                           ``cms`` and ``sysadmin``
==========================================  ==================================

Two further rules complete it:

- No domain module imports an ``apps.<app>.api`` module.  ``api/``, ``admin.py``,
  and the management commands are the composition points: they may import any
  app's models, services, and serializers.
- An upward import is allowed only inside a function, only where it breaks an
  app-level cycle, and only with a comment on the line above saying which one.
  There are four in the apps: ``User.membership_status`` and
  ``User.can_access_members_content`` reaching ``members``,
  ``accounts.services`` reaching the Wagtail site settings, and
  ``delete_member`` reaching ``payments.models`` for the refusal sentence.
  Three more are in the project package, which sits below every app:
  ``caldart.org`` and ``caldart.views`` read the Wagtail site settings, and
  ``caldart.mail`` writes the email log.

``backend/tests/test_app_layering.py`` enforces all of this with an ``ast`` pass
over ``backend/apps`` and ``backend/caldart``.  It lists every inline import by
name and fails both when an undeclared one appears and when a declared one stops
existing.

The services layer
------------------

Views and serializers validate input and shape output; they hold no domain
rules.  Anything that changes state or answers a domain question lives in
the app's ``services.py`` as plain functions, so the API, the management
commands, the seeders and the tests all run the same code:

- ``members.services.membership_status()`` is the one answer to "is this
  person a current member", and ``activate_term()`` is the only code that
  creates a membership term: a successful payment, an administrator's manual
  grant and the demo seeder all call it.
- ``payments.services.create_checkout()`` computes every total on the server,
  and ``mark_succeeded()`` is idempotent, so the browser's confirmation and a
  webhook for the same payment activate exactly one term.
- ``reminders.services.send_renewal_reminders()`` backs the command, the
  systemd timer and the portal's run button alike.
- ``aircraft.services.leader_status()`` builds the DART leader's status card;
  ``accounts.services`` creates an account, applies every rule about who may
  edit one, and sends the password mail; ``members.services`` owns the member
  record — registration, an administrator's create, edit, and delete — and
  ``sysadmin.services`` takes and restores backups and reports health.

A service refuses work by raising one of the ``DomainError`` subclasses in
``caldart/exceptions.py``, never an HTTP exception, so the same rule and the
same sentence reach a command, the Django admin and a test.  The API layer
translates them; :doc:`api-reference` gives the two shapes.

When one app changes another's state, it calls that app's service: a payment
reaches the membership tables only through ``activate_term()``.
:doc:`data-model` documents each service beside its models.


The public site frontend
========================

The templates are in ``backend/templates/``.  ``base.html`` is the shell
every page extends (skip link, header, and navigation, a footer with the
contact details), and its ``<html data-theme>`` carries the theme chosen in
Site Settings.  ``cms/<page_type>.html`` renders one page model,
``cms/blocks/*.html`` one StreamField block each, and
``cms/members_only_wall.html`` is what a visitor gets in place of a page they
may not read.  The navigation comes from ``site_chrome``: the live top-level
pages flagged *show in menus*, in tree order, then *Join* and either *Sign in*
or *Members*, depending on whether the visitor is signed in.

``base.html`` loads one bundle, ``frontend/src/site/main.ts``.  It imports
``styles/site.css``, the shared stylesheet plus the public site's editorial
rules, and adds progressive enhancement only: the mobile navigation toggle,
marking the current entry against the address bar, focusing the main content
from the skip link, and ``?theme=<slug>`` to preview a theme, which works
only where the template has set ``data-theme-preview="allowed"`` for a
website or system administrator.  Its pure helpers are in ``site/nav.ts``
so they can be unit tested.  :doc:`cms` and :doc:`theming` have the rest.

The donation page loads a second bundle beside it, ``src/site/donate.tsx``, which
mounts the React donation form from ``frontend/src/donate/`` on the page's
``#donate-app``: the one place the public site runs React.  The form lives beside
``site/`` and ``portal/`` rather than inside the portal, and reaches the portal's
components, its API client, and the checkout's provider tabs and payment panels
through the ``@/`` alias; it gets a query client and a toast queue of its own and
no router.  :ref:`cms-donate-page` has the details.


The portal SPA
==============

The portal lives in ``frontend/src/portal/``.  ``main.tsx`` mounts ``<App>``
on ``#portal-root``, and ``App.tsx`` wraps a browser router with the
basename ``/portal`` in the query client and the toast provider.

**Routing.**  Each feature exports a ``RouteObject[]`` from its own file in
``routes/``, and ``routes/index.tsx`` only concatenates them under one
``PortalLayout`` route, so adding a screen touches only its feature's route
file.  Paths are written without the ``/portal`` prefix:

========================  ======================================================
File                      Routes, and who may open them
========================  ======================================================
``auth.tsx``              ``/login``, ``/forgot-password``,
                          ``/reset-password``, ``/verify-email``: anyone;
                          ``/change-password``, ``/change-email``: signed in.
                          There is no sign-out address: the **Sign
                          out** button in the portal bar posts to
                          ``POST /auth/logout`` and then goes to ``/login``
``join.tsx``              ``/join``, ``/join/:step``: anyone; ``/renew``: signed
                          in
``dashboard.tsx``         ``/``: signed in
``profile.tsx``           ``/profile``, ``/profile/aircraft``: signed in
``payments.tsx``          ``/payments``: signed in
``leader.tsx``            ``/leader``, ``/leader/aircraft``: ``dart_leader`` or
                          ``account_admin``
``admin-members.tsx``     ``/admin/members``: ``account_admin`` or
                          ``dart_leader``; ``/admin/members/new``,
                          ``/admin/members/:id``: ``account_admin``
``admin-aircraft.tsx``    ``/admin/aircraft``, ``/admin/aircraft/:id``:
                          ``account_admin``
``admin-payments.tsx``    ``/admin/payments``, ``/admin/payments/list``,
                          ``/admin/payments/record``,
                          ``/admin/payments/members/:userId``,
                          ``/admin/payments/renewals``,
                          ``/admin/payments/reconciliation``,
                          ``/admin/payments/contributions`` and
                          ``/admin/payments/:id``: ``account_admin`` or
                          ``treasurer``
``admin-reminders.tsx``   ``/admin/reminders``: ``account_admin``
``admin-users.tsx``       ``/admin/users``, ``/admin/users/:id``: ``user_admin``
``system.tsx``            ``/system``: ``system_admin``
``not-found.tsx``         any other path
========================  ======================================================

**Auth screens.**  Every screen ``auth.tsx`` routes to renders through
``AuthShell`` (``features/auth/AuthShell.tsx``, styled by ``auth.css`` beside
it): a panel no wider than 26rem, centered in the frame, holding a centered
``h1`` title, an optional lede, one ``Card`` with the ``auth-card`` class for
the form, and an optional footer line below the card, such as the sign-in
page's link to join.  Inside the card, an ``auth__actions`` block stacks the
submit button at the card's full width above a centered secondary link.  A
visitor who is not signed in gets no rail, so ``PortalLayout`` adds the
``portal__frame--no-rail`` class to the frame, which makes it a single column
at every width; the page therefore has the whole window to center in.  The
join wizard's cards center themselves in it, and a ``.join-shell`` wrapper
around ``JoinWizard`` (``features/join/join.css``) caps the page header and
the step list at 46rem, centered on the same axis as the join card below,
rather than the header spanning the full window above a narrower, centered
card.  The account and verify steps use a narrower, 30rem card on that same
axis, so the header sits wider than the card on those two steps; every
other step's card is the full 46rem, so the edges line up there.

**Code splitting.**  A route names its page with React Router's ``lazy``
property rather than an ``element``, so the page's code is a chunk of its own
that the browser fetches the first time somebody opens that path.  The route
file imports the page's own module, not its feature's ``index.ts``, or the
barrel would drag the whole feature into the chunk.  Three files stay eager,
because they are where a visitor lands and a second request there would only
delay them: ``auth.tsx``, ``dashboard.tsx``, and ``not-found.tsx``.  Every
other route file loads on demand, which keeps the admin, system, and checkout
screens -- and the Stripe and PayPal React wrappers the checkout pulls in --
out of the bundle a member downloads to reach their dashboard.  A guard does
not hold its pages back: the router resolves a matched route's ``lazy``
module while it navigates, before the guard above it renders, so somebody the
guard then refuses has already fetched that page's chunk.  That costs one
request, not access -- the chunk is markup and JavaScript, and every piece of
data in it comes from an API call the server refuses.  The root route's
``hydrateFallbackElement`` shows ``components/Loading``, the same indicator
the guards use, while the router resolves the first page a visitor asks for.
That fallback covers that first load alone.  A move from one screen to
another inside the portal shows nothing new: the router holds the screen the
visitor is on until the next page's chunk arrives, and the portal adds no
progress bar over it.

**Guards.**  ``RequireAuth``, in ``auth/guards.tsx``, wraps every route that
needs a session and sends an anonymous visitor to
``/login?next=<the path they asked for>``; the sign-in page returns them
there.  ``RequireRole`` wraps each role-gated route file and shows a 403 page
naming the role.  Both wait for ``GET /auth/me`` to settle, so a slow answer
never flashes the sign-in page, and ``system_admin`` satisfies every role.
When the check fails outright -- a 5xx or a dropped connection, after the
retries -- they show "We could not check your sign-in" with a **Try again**
button instead of redirecting, so an outage never reads as a lost session;
:doc:`api-auth` describes the three outcomes in full.  The guards are a
courtesy: the API enforces every permission itself.

**Server state.**  Everything from the API goes through TanStack Query.
``auth/useAuth.ts`` wraps ``GET /auth/me`` under the key ``['auth', 'me']``,
the portal's single notion of who is signed in.  Signing in, registering, and
signing out clear the whole cache and write the result into that key, so
nothing cached for one person is shown to the next.

**The API client.**  ``api/client.ts`` is the only code that calls
``fetch``.  It prefixes ``/api/v1``, sends the session cookie, performs the
CSRF bootstrap, encodes JSON, and turns any non-2xx response into an
``ApiError`` with the status, the DRF error body, and ``fieldErrors`` keyed
by field for forms.  A 403 whose ``detail`` starts ``CSRF Failed`` is the one
response it retries: it fetches a token again and resends the request once,
which recovers a cookie that has gone stale mid-session.

A successful response has to be JSON or nothing: a 204, or an empty body,
becomes ``null``, and anything else that will not parse as JSON raises
``UnexpectedResponseError`` carrying the status and the content type.  A
truncated body or an HTML page from a proxy therefore reaches the screen as
its error state, rather than as a ``null`` or a string the caller's declared
type says is an object.  The error deliberately does **not** extend
``ApiError``, because it carries no server message for a screen to show.
``api/types.ts`` types every API object by hand, in step with the
serializers.

**Features.**  A directory under ``features/`` holds one feature's pages and
components, an ``api.ts`` of query hooks, its stylesheet, its tests beside
the files they test, and an ``index.ts`` of what the route files use:

======================  ======================================================
``auth``                sign-in, sign-out, password reset and change
``join``                the join wizard (account, profile, pay, done) and the
                        renew page
``checkout``            the ``<Checkout>`` that join and renew share: plan and
                        contribution, then one panel per payment provider
``dashboard``           the member's home: status, payments, and the
                        members-only pages from ``GET /api/v1/site/config``
``profile``             the profile form, the fieldsets the admin member
                        screens share with it, and *My aircraft*
``aircraft``            the aircraft picker, form, and insurance and service
                        chips that the profile, leader, and admin screens reuse
``leader``              the DART leader's member check and aircraft check
``admin-*``             the members, aircraft, payments, reminder-log, and users
                        screens
``system``              the System page: health, backups, and reminders
======================  ======================================================

Shared code sits outside ``features/``: ``components/`` holds the primitives
every screen uses (``Page``, ``Card``, ``Field``, ``Button``, ``IconButton``,
``DeleteButton``, ``StatusChip``, ``DataTable``, ``PanelButton``, ``ColumnChooser``,
``FilterBar``, ``RunActionsTable``, ``Money``, ``DateText``, ``EmptyState``, and
``Toast``), and ``choices.ts`` holds the one set of labels for certificate,
medical, IFR, rating, and role codes, and the list of California counties.
``components/icons.tsx`` holds the inline SVG icons -- ``TrashcanIcon``,
``ArrowUpIcon``, and ``ArrowDownIcon`` -- each ``aria-hidden``, drawn in
``currentColor``, square, and ``1.25em`` on a side unless the caller asks for
another size, so the portal ships no icon dependency.
``IconButton`` is a control that shows one of those icons and nothing else: a
``<button>`` with the ``icon-button`` class rather than a ``Button``, with no
border, no background, and the muted text color until hover or keyboard focus
brings it forward.  Its required ``label`` is the whole of the accessible name
and the tooltip, unless the caller passes a ``title`` of its own.  Use it where
the row already says what the control acts on -- an attached aircraft, a person
on a DART -- so a list of records reads as a list rather than as a wall of
buttons.  ``DeleteButton`` is every Remove and Delete control in the portal: a
bare ``IconButton`` trashcan where the control sits in a row or on a form line,
and a quiet ``Button`` with the trashcan leading its words where the action is
confirmed, with the trashcan at the text size there rather than at the larger
size a bare icon takes.  ``PanelButton`` is a quiet small ``Button`` with
``aria-expanded`` and ``aria-controls`` and the captioned panel (a
``<fieldset>`` with its ``legend``) it opens under itself.  The panel's contents
mount only while it is open, and receive a function that closes it; the panel
closes on a click outside it or on Escape, and closing it while the focus is
inside hands the focus back to the button.  ``ColumnChooser`` drives a report
table and its two exports from one set of ticks.  It is three ``PanelButton``\ s
side by side in a ``.column-chooser`` cluster: **Columns** holds the checkboxes
and **Reset to the default columns**; **Load columns** lists the signed-in
user's named sets of the report's columns as buttons, each with a trashcan, and
applies and closes on a pick; **Save columns** holds a name box and a **Save**
button that keeps the chosen columns under that name and closes on success.
The sets come from ``/reports/{slug}/column-sets``, read only once **Load
columns** first opens.
``components/Loading.tsx`` sits beside them:
the guards and the route table are its only callers, and both import it by
name, as every file in the directory is imported -- there is no barrel.
``components/useClickOutside.ts`` is the hook behind that dismissal, for any
popover that wants it.  ``components/useDebounced.ts`` sits beside the
primitives too, a hook rather than something a page renders: it returns a
value only once it has held still for a delay, which defaults to the
``SEARCH_DEBOUNCE_MS`` of 250 milliseconds that every search box uses.  The checkout panel passes 500 milliseconds instead, so
changing the amount does not create a payment intent per keystroke.
``RunActionsTable`` is the table of what a scheduled run did, or would do,
behind its summary counts: one row per email sent or charge taken, with a column
for each action's ``detail`` (the report sent, or the DART whose roster went)
when the caller names its heading.

**Filters and reports.**  ``reports/`` holds what every report shares in the
portal.  ``reports/definitions.ts`` declares ``REPORTS``, one
``ReportDefinition`` per report the server registers (``members``,
``aircraft``, ``payments``, ``reconciliation``, and ``contributions``), each
with its label, whether its columns can be chosen, whether it takes
``?period=``, and its ``filters``: the single list of that report's filter
fields.  A ``FilterField`` names the query parameter it sends as its ``key``,
and its ``kind`` says how it is drawn: ``search`` (a text box), ``select`` (a
drop-down whose blank first option reads *Any*, or the field's
``placeholder``), ``multiselect`` (a ``<select multiple>`` six rows tall with no
blank option, whose chosen values travel joined with commas, in the order the
box lists them, both in the address and in a subscription's ``filters``;
choosing none sends nothing), ``number`` (digits only; with ``isDollars`` the box takes
whole dollars and sends cents), ``date``, or ``toggle`` (a checkbox that sends
``true`` or nothing).  A field marked ``subscriptionOnly``, the period of the
payments and contributions reports, belongs to the form that subscribes
somebody to a report; ``listFilters`` leaves it out for a list page.

``components/FilterBar.tsx`` is the only filter UI.  It draws a report's
fields, with choices only the server knows, such as the DARTs or the plans,
passed in through its ``options`` prop, and applies every change itself: a
select, a multiselect, a date, or a toggle at once, a text or number box once the typing has
held still for ``SEARCH_DEBOUNCE_MS``.  There is no Apply button, and
**Reset to Defaults** empties every field.  The bar aligns its controls to
their bottom edge, and a field's ``hint`` is its control's ``title`` rather
than a line under it, so the controls of a row line up.  The member county
filter is the one ``multiselect``, so a DART that covers two counties can ask
for both.  ``components/useUrlFilters.ts`` keeps a list
page's filters in the query string, so a filtered view is a link: it reads
the keys it is given, and writing them drops the empty ones and ``page``, so a
change of filter returns the list to its first page, while leaving any other
parameter, such as ``ordering``, alone.
``components/useUrlListPosition.ts`` keeps a server-paged list's ``ordering``
and ``page`` beside them the same way: a page that is not a whole number of at
least 1 reads as the first, a change of order returns to the first page, and
``useFirstPageWhenMissing`` goes back to the first page when the list answers
404 for a page past its end.  Its ``sort`` feeds ``DataTable``'s ``sort`` prop,
so the header arrow follows the address when the back button changes the
order.

``reports/api.ts`` is the one client for ``/api/v1/reports/``
(:doc:`api-reference`): ``useReports`` lists the reports the caller may read,
``useReportColumns`` fetches a report's column registry once and keeps it, and
``reportExportUrl`` builds every export href, leaving out empty values and
``page`` and joining the chosen ``columns`` with commas.

**Navigation.**  ``nav.ts`` declares every entry in ``NAV_ITEMS`` with the
roles that may see it (an empty list means any signed-in user) and a group:
*Membership*, *Operations*, *Administration*, or *System*.
``layout/PortalLayout.tsx`` shows what the user's roles allow, as a rail on
a wide screen and a drawer on a phone.  Keep an entry's roles the same as
the ``RequireRole`` on its route.


Background work
===============

There is no task queue, worker process or scheduler daemon.  Work runs
inside a request or a management command, and mail is sent synchronously by
whichever one causes it.

**Renewal reminders.**  ``send_renewal_reminders`` emails members at five
stages around expiry — two months before, a month before, in the last week,
once the term has run out, and once a month later — each stage a span of expiry
dates rather than one date, so every term passes through it (:ref:`the spans
<reminders-stages>`).  It
records every message in ``ReminderLog``, one row per user, term, and kind,
so a second run sends nothing twice, and it marks lapsed terms expired;
lifetime members are skipped.  ``deploy/systemd/caldart-reminders.timer``
runs it daily at 07:00 in production, ``make reminders`` in development
(``TODAY=YYYY-MM-DD`` scans as of another date, ``DRY_RUN=1`` rehearses),
and a system administrator can run it from the portal's System page
(:doc:`reminders`).

**Backups.**  ``db_backup`` writes a gzipped ``pg_dump`` into ``BACKUP_DIR``
(``backups/`` by default), inside the Compose database container while
``DB_BACKUP_VIA_DOCKER`` is on, the default, and with a local ``pg_dump``
otherwise.  ``make backup`` runs it, and so does the System page, which also
lists and downloads dumps.  No backup timer ships in ``deploy/``
(:doc:`backup-restore` shows how to add one), and restore and reset are
command-line only, so nothing destructive is one click away.  ``health``
reports database connectivity, pending migrations, free disk space and the
last backup.


Where to read next
==================

- :doc:`setup` for a working checkout, the make targets and the commands;
  :doc:`configuration` for every environment variable.
- :doc:`data-model` and :doc:`api-reference`, the two references to keep
  open.
- :doc:`payments-setup`, :doc:`cms`, :doc:`theming`, :doc:`reports` and
  :doc:`reminders`, one page per subsystem.
- :doc:`testing`, :doc:`deployment` and :doc:`backup-restore` for testing
  , running, and looking after it; :doc:`roadmap` for what is left out.

Coding conventions live in ``CLAUDE.md`` and ``.claude/rules/`` at the
repository root.
