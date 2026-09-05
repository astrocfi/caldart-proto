=================
The CMS (Wagtail)
=================

``backend/apps/cms`` is the public website: the Wagtail page models, the
StreamField blocks they are built from, the site settings that carry the
organisation details and the theme, the members-only wall, and the templates
under ``backend/templates/``.  It implements PLAN §4.6, §6.10, §7 and §9.

.. contents::
   :local:
   :depth: 2


Layout
======

::

  backend/apps/cms/
    models.py            page types, MembersOnlyMixin, SiteSettings
    blocks.py            StreamField blocks and the body stream
    forms.py             the page form that hides restricted blocks
    permissions.py       the website_admin Wagtail grant
    context_processors.py   site_settings / theme / nav for every template
    seed.py              site root + settings row (called by seed_demo)
    api/views.py         GET /api/v1/site/config
    management/commands/seed_content.py    the example site
  backend/templates/
    base.html            the public shell: header, nav, footer
    404.html, 500.html
    cms/<page_type>.html one per page model
    cms/blocks/*.html    one per block
    cms/includes/        wordmark, page header, section nav
  frontend/src/
    site/main.ts         nav toggle, current page, theme preview
    site/nav.ts          the pure helpers those use
    styles/site.css      public-site styles (imports styles/index.css)


Page models
===========

Every page type subclasses ``BasePage``, which supplies two things: the
``base_form_class`` that enforces block permissions, and ``body_headings`` /
``show_on_this_page`` for the "on this page" rail.

===================  ========================================================
Model                Notes
===================  ========================================================
``HomePage``         The site root.  Hero, ``mission_statement``,
                     ``concept_of_operations`` (a stream of ``step`` blocks)
                     and ``tax_status``.  ``featured_news`` returns the three
                     most recent live, public news posts.
``StandardPage``     ``intro`` + ``body``; carries ``MembersOnlyMixin``.
``NewsIndexPage``    Paginates its child posts, ``NEWS_PAGE_SIZE`` at a time,
                     and hides members-only posts from visitors who could not
                     open them.
``NewsPage``         ``date``, ``intro``, ``image``, ``body``; carries
                     ``MembersOnlyMixin``.  Only allowed under a news index.
``DartIndexPage``    Renders its children as a table.
``DartPage``         ``dart`` (FK to ``members.Dart``), ``leader_name``,
                     ``leader_contact``, ``body``.  ``airport_identifier``
                     and ``city`` are read through the FK, so the page never
                     duplicates the membership database.
``ContactPage``      ``intro`` + ``body``; the address block comes from
                     ``SiteSettings``.
===================  ========================================================

``subpage_types`` and ``parent_page_types`` are declared so editors cannot
build a nonsensical tree — a news post only fits under a news index, a DART
page only under a DART index.


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
``none``         A signed-in account with no membership at all.  Offers
                 join.
===============  =========================================================

Who gets through is ``User.can_access_members_content`` (PLAN §4.1): a current
membership, *or* any role beyond plain ``member``.  A DART leader with no
membership of their own can still read the handbooks.

Wagtail's native page privacy still applies on top of this; the two are
independent.

Add the mixin to a new page type by listing it first in the bases and adding
its panel::

    class HandbookPage(MembersOnlyMixin, BasePage):
        content_panels = [
            *Page.content_panels,
            FieldPanel("body"),
            MultiFieldPanel(MembersOnlyMixin.members_only_panels, heading="Access"),
        ]


Blocks
======

``blocks.ContentStreamBlock`` is the body offered on every editable page, and
matches the list in PLAN §4.6: ``heading``, ``paragraph``, ``image``,
``quote``, ``cta``, ``document``, ``two_columns``, ``embed`` and ``raw_html``.
``ColumnStreamBlock`` is the reduced set allowed inside a two-column block, so
columns cannot nest.

Each block names its own template under ``cms/blocks/``; nothing renders from a
default.  ``heading`` computes a slug anchor through ``heading_anchor`` so long
pages get a table of contents, and ``stream_headings`` collects the H2 headings
for the aside.

Adding a block
--------------

#. Write the block class in ``blocks.py``, with a ``Meta`` that sets ``icon``,
   ``label`` and ``template``.
#. Add it to ``ContentStreamBlock`` (and to ``ColumnStreamBlock`` if it makes
   sense inside a column).
#. Write ``backend/templates/cms/blocks/<name>.html``.  Use the semantic
   tokens; do not introduce colours (see :doc:`theming`).
#. Style it in ``frontend/src/styles/site.css``.
#. ``manage.py makemigrations cms`` — a StreamField change is a migration even
   though the column type does not change.
#. Cover it in ``backend/tests/test_cms_pages.py``; the
   ``test_standard_page_renders_every_block_type`` test builds one of each.

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

#. Subclass ``BasePage`` (plus ``MembersOnlyMixin`` if it can be closed) in
   ``models.py``.
#. Declare ``content_panels``, ``search_fields``, ``template``, and
   ``parent_page_types`` / ``subpage_types``.
#. Add ``__str__`` — ruff's ``DJ008`` asks for one on every concrete model.
#. Write ``backend/templates/cms/<snake_name>.html`` extending ``base.html``.
#. ``manage.py makemigrations cms``.
#. Extend ``seed_content`` if the example site should have one.
#. Test that it renders, and that its permissions behave.


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
    The theme slug, defaulting to ``sierra``.  ``base.html`` and
    ``portal.html`` put it on ``<html data-theme="...">``.

``nav``
    ``build_nav(request)``: the live top-level pages flagged *show in menus*
    as ``kind="page"``, then ``Join`` → ``/portal/join`` and ``Log in`` /
    ``Members`` → ``/portal/`` as ``kind="portal"``.  ``base.html`` renders
    the first group as links and the second as buttons.

``can_preview_theme``
    True for website and system administrators.  ``base.html`` turns it into
    ``data-theme-preview="allowed"``, which is what lets ``site/main.ts``
    honour ``?theme=<slug>``.

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
     "theme": "sierra",
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
the ``website_admin`` group (which is just the role group from PLAN §4.1):

* ``wagtailadmin.access_admin`` and ``cms.change_sitesettings`` on the group
  itself — not ``wagtailcore.change_site``, because editing hostnames belongs
  to a system administrator;
* add / change / publish / bulk-delete / lock on the **tree root** page, so
  the grant cascades to every current and future page;
* add / change / choose on the **root collection** for images and documents.

It runs twice: from the ``cms.0004_website_admin_permissions`` data migration,
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

Builds the example site from PLAN §4.6 and is safe to run repeatedly:
``upsert_page`` looks each page up by slug under its parent, updates it in
place and publishes a revision, and the DART section deletes any page whose
team has gone.  ``make seed`` runs it after ``seed_demo``.

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
``test_cms_seed_content.py``     Tree shape, the copy the plan requires,
                                 and running the command twice.
``test_cms_permissions.py``      The grant, reaching ``/admin/``, editing
                                 and publishing as ``website_admin``, and
                                 the raw-HTML restriction.
``test_site_config.py``          ``/site/config`` for every caller.
===============================  ======================================

Backend tests do not need a frontend build: ``conftest.py`` stubs the Vite
manifest when ``frontend/dist`` is missing.
