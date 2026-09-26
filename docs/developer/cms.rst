=================
The CMS (Wagtail)
=================

``backend/apps/cms`` is the public website: the Wagtail page models, the
StreamField blocks they are built from, the site settings that carry the
organization details and the theme, the members-only wall, and the templates
under ``backend/templates/``.  :doc:`architecture` shows where the public site
sits in the whole system, :doc:`data-model` lists the page models' fields, and
:doc:`theming` covers the stylesheets.


Layout
======

::

  backend/apps/cms/
    models.py            page types, MembersOnlyMixin, SiteSettings
    blocks.py            StreamField blocks and the body stream
    forms.py             the page form that hides restricted blocks
    permissions.py       the website_admin Wagtail grant
    wagtail_hooks.py     the members-only guard on document downloads
    context_processors.py   site_settings / theme / nav for every template
    seed.py              site root + settings row (called by seed_demo)
    seed_content_data.py the example site's copy, as page specs
    api/views.py         GET /api/v1/site/config
    management/commands/seed_content.py    the example site
  backend/templates/
    base.html            the public shell: panel, masthead, nav bar, footer
    404.html, 500.html
    cms/<page_type>.html one per page model
    cms/blocks/*.html    one per block
    cms/includes/        page header, section nav
  frontend/src/
    site/main.ts         nav toggle, current page, theme preview
    site/nav.ts          the pure helpers those use
    site/donate.tsx      mounts the donation form on the donate page
    donate/              the donation form itself (React)
    styles/site.css      public-site styles (imports styles/index.css)
  backend/static/img/caldart-logo.png   the masthead logo


Page models
===========

Every page type subclasses ``BasePage``, which supplies two things: the
``base_form_class`` that enforces block permissions, and ``body_headings`` /
``show_on_this_page`` for the "on this page" rail.

===================  ========================================================
Model                Notes
===================  ========================================================
``HomePage``         The site root.  The welcome box (``hero_heading``,
                     ``hero_lede``, ``hero_image``, ``mission_statement``
                     , ``welcome_body``, and three calls to action, the first of
                     them ``urgent_cta_*``), ``missions_flown`` (a stream of
                     ``mission`` blocks) and ``tax_status``.
                     ``featured_news`` returns the three most recent live,
                     public news posts, members-only ones excluded whoever is
                     looking; ``events_soon`` returns the three soonest live
                     ``EventPage`` records dated today or later, and
                     ``event_index`` the calendar they link to; ``darts`` and
                     ``plans`` fill the sidebar's team finder and price list.
``StandardPage``     ``intro`` + ``body``; carries ``MembersOnlyMixin``.
``NewsIndexPage``    Paginates its child posts, ``NEWS_PAGE_SIZE`` at a time,
                     and hides members-only posts from visitors who could not
                     open them.
``NewsPage``         ``date``, ``intro``, ``image``, ``body``; carries
                     ``MembersOnlyMixin``.  Only allowed under a news index.
``EventIndexPage``   The calendar.  ``upcoming()`` is its live children dated
                     today or later, soonest first, and ``past()`` the rest,
                     most recent first; the page lists everything upcoming and
                     paginates the past ``EVENT_PAGE_SIZE`` at a time.
``EventPage``        ``date``, ``time``, ``location``, ``intro``, ``body``.
                     ``EventPage.objects`` is an ``EventPageManager`` carrying
                     ``upcoming()`` and ``past()``, which is what the home
                     page's sidebar and the calendar both read.  ``is_past``
                     says whether the day is over and ``when_and_where`` joins
                     the place and the time into one line.  Only allowed under
                     an event index.
``DartIndexPage``    ``intro`` + ``body`` above its children, which it renders
                     as a table.
``DartPage``         ``dart`` (nullable ``SET_NULL`` FK to ``darts.Dart``),
                     ``leader_name``, ``leader_contact``, ``body``.
                     ``airport_identifiers`` is read through the
                     FK, so the page never duplicates the membership database.
                     Deleting the DART leaves the page with no DART attached.
``ContactPage``      ``intro`` + ``body``; the address block comes from
                     ``SiteSettings``.
``DonatePage``       The public donation page (see `The donation page`_).
                     ``intro`` (rich text) above the form and ``thanks``
                     (rich text) shown in its place once a gift has gone
                     through.  Allowed under the home page or a standard
                     page; takes no children.
===================  ========================================================

``subpage_types`` and ``parent_page_types`` are declared so editors cannot
build a nonsensical tree — a news post only fits under a news index, a DART
page only under a DART index.


.. _cms-donate-page:

The donation page
=================

``cms/donate_page.html`` renders the page's ``intro``, then the page's ``thanks``
inside ``<div data-donate-thanks hidden>``, then the mount point::

    <div id="donate-app" data-config-url="/api/v1/donations/config"
         data-return-url="/donate/"></div>

``data-return-url`` is the page's own URL: a payment method that leaves the page
(a card that asks for 3-D Secure) comes back to it with ``payment_id`` and
``token`` in the query string.  The template loads a third Vite entry,
``src/site/donate.tsx``, through ``{% vite_asset %}`` in ``extra_head``; nothing is
inline, because the Content Security Policy forbids an inline script.  A
``<noscript>`` line says how else to give.

The script mounts ``DonationForm`` (``frontend/src/donate/``) with a TanStack
Query client and a toast queue of its own and no router.  The form reads
``GET /donations/config``, takes the amount and the giver's details, and pays
through the portal's own provider tabs and Stripe, PayPal, and mock panels, which
take their endpoints as a prop (``PaymentEndpoints``) so the page's calls go to
``/donations/`` with the token rather than to ``/payments/``.  Once a gift has gone
through it replaces itself with the receipt sentence and un-hides the thanks.
The endpoints are in :ref:`api-public-donations`; what a giver sees is in
:doc:`/user/member/public-website`.

The members-only wall
=====================

``MembersOnlyMixin`` adds a ``members_only`` boolean and overrides ``serve``:

.. code-block:: python

   def serve(self, request, *args, **kwargs):
       if self.members_only and not user_can_access_members_content(request.user):
           return self.serve_members_only_wall(request)
       return super().serve(request, *args, **kwargs)

The wall renders ``cms/members_only_wall.html`` with **HTTP 403** and one call
to action, chosen by ``members_wall_state``:

===============  =========================================================
``wall_state``   Shown to
===============  =========================================================
``anonymous``    A signed-out visitor.  Offers sign-in (with ``?next=``)
                 and join.
``expired``      A signed-in member whose term has run out.  Offers renew,
                 and names the expiry date.
``friend``       A signed-in friend of CalDART (:ref:`kinds of account <account-kinds>`).
                 Says "Friends of CalDART can read this page by becoming a
                 member." and offers **Make me a member**, a link to
                 ``/portal/membership/join``.
``none``         A signed-in account with no membership at all.  Offers
                 join.
===============  =========================================================

Who gets through is ``User.can_access_members_content`` (:doc:`data-model`): a current
membership, *or* any role beyond plain ``member``.  A DART leader with no
membership of their own can still read the handbooks, and so can a friend who
holds a staff role; a friend with only the ``member`` role gets the wall.

Wagtail's native page privacy still applies on top of this; the two are
independent.

Add the mixin to a new page type by listing it first in the bases and adding
its panel::

    class HandbookPage(MembersOnlyMixin, BasePage):
        body = StreamField(ContentStreamBlock(), blank=True)

        content_panels = [
            *Page.content_panels,
            FieldPanel("body"),
            MultiFieldPanel(MembersOnlyMixin.members_only_panels, heading="Access"),
        ]


Members-only documents
----------------------

The switch closes a page; the files it links to are closed by their collection.
``wagtail_hooks.guard_members_only_documents`` is a ``before_serve_document``
hook, which Wagtail runs before it hands a document over:

.. code-block:: python

   @hooks.register("before_serve_document")
   def guard_members_only_documents(document, request):
       if not collection_is_members_only(document.collection):
           return None
       if user_can_access_members_content(request.user):
           return None
       context = {"page": {"title": document.title}, **members_wall_context(request.user)}
       return TemplateResponse(request, "cms/members_only_wall.html", context, status=403)

``collection_is_members_only`` is true for the collection named
``MEMBERS_ONLY_COLLECTION_NAME`` (``Members only``) and for every collection
beneath it: a descendant's materialized path starts with its ancestor's, so one
prefix test covers the whole subtree.  A document in any other collection, and
a document with no collection at all, is public.

The refusal is the page wall rendered from the same template and the same
``members_wall_context``, with the document's title in place of a page's, so a
member who follows a link to a file they may not download is offered the same
next step.  The file's bytes are never sent.

Three things keep the guard on the only path to the file:

* ``WAGTAILDOCS_SERVE_METHOD = "serve_view"`` in ``settings/base.py``, so
  ``document.url`` is always Wagtail's ``/documents/<id>/<filename>`` view and
  never a direct ``/media/`` URL, whatever the storage backend;
* ``deploy/nginx/caldart.conf`` returns 404 for ``/media/documents/`` and
  ``deploy/apache/caldart.conf`` denies that directory, so the uploads on disk
  are unreachable without the view (:doc:`deployment`);
* ``seed_content`` creates the collection, so the copy that tells editors to
  upload into it is true of a fresh site.

Wagtail's own collection privacy still applies on top of this, and is the way
to close a collection to everyone but a Wagtail group or a password.


Blocks
======

``blocks.ContentStreamBlock`` is the body offered on every editable page:
``heading``, ``paragraph``, ``image``, ``quote``, ``cta``, ``document``,
``two_columns``, ``embed``, and ``raw_html``.  ``ColumnStreamBlock`` is the
reduced set allowed inside a two-column block, so columns cannot nest, and
The home page has one stream of its own: ``MissionStreamBlock``, whose
``mission`` blocks pair a ``year`` with the text of what was flown and render
as the rows of one table.

``cta`` (``CTABlock``) is the call to action: a ``label``; a target that is
either a ``page`` from the tree or a ``url`` (an external address, or a path
such as ``/portal/join``); a ``style`` of ``primary`` (the default),
``secondary`` or ``quiet``; and an optional ``note`` printed small under the
button.  Saving one with neither a page nor a URL fails validation.

Each block names its own template under ``cms/blocks/``, with one deliberate
exception: ``raw_html`` is a plain ``RawHTMLBlock`` and emits its content
unwrapped, which is the whole point of it.  ``heading`` computes a slug anchor
through ``heading_anchor`` so long pages get a table of contents, and
``stream_headings`` collects the H2 headings for the aside.

Adding a block
--------------

:ref:`extending-block` in :doc:`extending` has the recipe and a skeleton: the
block class and its ``Meta``, the stream it joins, its template and styles, the
migration a StreamField change still needs, and the test that renders one of
every block.

Restricting a block
-------------------

``raw_html`` is "website administrators only", and Wagtail has no per-block
permission.  ``forms.RestrictedBlocksPageForm`` is the page's
``base_form_class``: Wagtail hands the form the editing user as ``for_user``,
and when that user fails ``can_use_raw_html`` the form rebuilds each
StreamField's block without the names in ``blocks.RESTRICTED_BLOCK_TYPES`` and
swaps the widget to match.  Django deep-copies form fields per instance, so
this affects one editing session and never the shared block definition.

To restrict another block, add its name to ``RESTRICTED_BLOCK_TYPES``.


Adding a page type
==================

:ref:`extending-page-type` in :doc:`extending` has the recipe and a skeleton:
the bases to subclass, the panels, search fields, template, and tree
constraints to declare, the migration, the ``seed_content`` entry, and the
tests for rendering and access.


Navigation and site settings
============================

``context_processors.site_chrome`` runs on every server-rendered template and
supplies four names:

``site_settings``
    The ``SiteSettings`` row for the request's site, or ``None`` before
    ``migrate`` has created one.  Read through ``get_site_settings(request)``,
    never ``SiteSettings.for_request`` — the latter would write a row during a
    GET.

``theme``
    The theme slug, defaulting to ``duty``.  ``base.html`` and
    ``portal.html`` put it on ``<html data-theme="...">``.

``nav``
    ``build_nav(request)``: ``Home`` -> ``/``, then the live top-level pages
    flagged *show in menus* as ``kind="page"``, each carrying its own in-menu
    children as ``children`` for a drop-down.  A menu page behind the
    members-only wall is moved to the end as ``kind="portal"``, beside the
    portal link itself -- ``Member portal`` -> ``/portal/`` for a signed-in
    visitor, ``Sign in`` -> ``/portal/login`` for an anonymous one.  That title
    is ``PORTAL_TITLE``, and it deliberately does not read ``Members``: a site
    whose members area is a content page would otherwise carry the same word
    twice in one bar.  ``base.html`` renders the first group as the navigation
    bar's links and the second at its right-hand end, with a
    ``Welcome, <first name>`` greeting ahead of it for a signed-in reader.  An
    entry is marked ``active`` when the request path starts with its URL, and
    ``Home`` only when the path is exactly ``/``.

``can_preview_theme``
    True for website and system administrators.  ``base.html`` turns it into
    ``data-theme-preview="allowed"``, which is what lets ``site/main.ts``
    honor ``?theme=<slug>``.

.. warning::

   Error templates render without the full context — Django's 500 handler
   passes neither a request nor context processors.  Use ``{% firstof %}``
   rather than the ``default`` filter when falling back to a literal: a
   missing *filter argument* raises, where a missing variable does not.  And
   use ``{% comment %}``, not ``{# ... #}``, for anything longer than one
   line — Django's hash comment does not span lines and the rest leaks into
   the page.


``GET /api/v1/site/config``
===========================

The one endpoint the portal calls before it has a user, so it is ``AllowAny``:

.. code-block:: json

   {
     "org_name": "The California DART Network",
     "theme": "duty",
     "contact_email": "info@caldart.example.org",
     "nav": [{"title": "About Us", "url": "/about/", "active": false, "kind": "page"}],
     "members_pages": [{"title": "Members", "url": "/members/"}]
   }

``members_pages`` lists the live members-only pages, and is empty for anyone
who could not open them — the same ``can_access_members_content`` test the
wall uses.


Editor permissions
==================

``permissions.grant_website_admin_permissions`` hangs the Wagtail rights off
the ``website_admin`` group (the same Django group that holds the role):

* ``wagtailadmin.access_admin`` and ``cms.change_sitesettings`` on the group
  itself — not ``wagtailcore.change_site``, because editing hostnames belongs
  to a system administrator;
* add / change / delete on ``wagtailredirects.Redirect``, so an editor who
  renames a page can point the old address at the new one;
* add / change / publish / bulk-delete / lock on the **tree root** page, so
  the grant cascades to every current and future page;
* add / change / choose on the **root collection** for images and documents.

Wagtail's redirect signal handlers do most of that work unprompted:
``WAGTAILREDIRECTS_AUTO_CREATE`` keeps its default of true, so publishing a
slug change or moving a page writes a permanent redirect from the old URL of
that page and of every page below it.  The three permissions are what puts
**Settings → Redirects** in the menu, so an editor can see those rows and fix
the ones automation cannot.

It runs twice: from the ``cms.0003_website_admin_permissions`` data migration,
so a fresh database is correct after ``migrate`` alone, and again from
``seed_content``.  It takes an optional ``apps`` registry so the migration can
pass historical models, which is why every lookup is written against plain
fields rather than manager helpers.  Permissions are fetched with
``get_or_create``: a data migration runs before Django's ``post_migrate``
handler has created them, and Django's own step skips codenames that already
exist.

``system_admin`` users are Django superusers, so they bypass all of this.


``manage.py seed_content``
==========================

Builds the example site, and is safe to run repeatedly::

    Home
      About Us
        History
        DARTs                (index + one page per DART)
        Directors and Officers
      News                   (index + three posts)
      Join CalDART
      Donate
      Sponsors
      Contact Us
      Members                (members only)
        Members Only
        Documents and Links

``upsert_page`` looks each page up by slug under its parent, updates it in
place and publishes a revision, and the DART section deletes any page whose
team has gone.  ``/donate/`` is a ``DonatePage``; a page of another type left at
that slug is deleted first so the donation page takes its place.  ``make seed`` runs it after ``seed_demo``.

.. _cms-seed-data:

Every word of the copy lives in ``seed_content_data.py``, which holds no logic:
each page is a frozen ``PageSpec`` naming its slug, title, intro, menu, and
members-only flags and a tuple of ``BlockSpec`` body blocks, built by the
``rich``, ``heading``, ``quote``, and ``cta`` helpers; a news post pairs a
``PageSpec`` with how many days ago it was posted.  The command reads the specs
and writes the pages, so changing a sentence never touches the code that builds
the tree.  The donation page's rich-text intro and thanks are a
``DonatePageSpec`` of their own.  Site settings come from the same module's
``SITE_SETTINGS``.

It also calls ``ensure_members_only_collection``, so the ``Members only``
document collection exists on a fresh site and the members-area copy can tell
editors to upload handbooks and forms into it.  The website-administrator grant
is on the root collection and cascades to it.

The copy is example content — paraphrased, not lifted — and site settings are
only filled in where they are still blank, so a theme or phone number an
administrator has changed survives a re-seed.


Testing
=======

===============================  ======================================
``test_cms_pages.py``            Page rendering, every block type, the
                                 wall for each state, nav composition,
                                 theme, error pages.  Also holds the
                                 page-building helpers the other CMS
                                 test modules import.
``test_cms_seed_content.py``     Tree shape, the copy each page must
                                 carry, and running the command twice.
``test_cms_permissions.py``      The grant, reaching ``/admin/``, editing,
                                 and publishing as ``website_admin``, and
                                 the raw-HTML restriction.
``test_site_config.py``          ``/site/config`` for every caller.
===============================  ======================================

Backend tests do not need a frontend build: ``conftest.py`` stubs the Vite
manifest when ``frontend/dist`` is missing.

Related
=======

:doc:`api-system` documents ``GET /site/config``, which reports the
navigation and members-only pages this chapter builds.
