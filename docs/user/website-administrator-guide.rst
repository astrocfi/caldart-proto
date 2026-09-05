###########################
Website administrator guide
###########################

This guide is for people who hold the ``website_admin`` role: you look after
the public |org| website — the pages, their words and pictures, the members-only
area, and the organisation details that appear in the header and footer.

You do not need to know anything about the member database, payments or
reports.  Those live in the member portal and belong to other roles.

.. contents::
   :local:
   :depth: 2


Signing in
==========

The content management system is Wagtail, and it lives at ``/admin/``:

* production: ``https://<your-site>/admin/``
* local development: ``http://localhost:8000/admin/``

Sign in with the same email address and password you use for the member
portal.  If Wagtail sends you back to the login form with "You do not have
permission to access the admin", your account is missing the ``website_admin``
role — ask a user administrator to add it.

The demo data ships with ``webadmin@example.org`` (password ``caldart-demo``)
already in the role.

.. note::

   ``/admin/`` is the *content* admin.  ``/portal/`` is the member portal and
   ``/django-admin/`` is the low-level Django admin, which only system
   administrators use.


The page tree
=============

Everything on the public site is a page, and every page hangs off the home
page.  Choose **Pages** in the left-hand menu to walk the tree::

    Home
      About Us
        History
        DARTs                       one page per team
        Directors and Officers
      News                          the index; posts live under it
      Join CalDART
      Donate
      Sponsors
      Contact Us
      Members                       members only
        Members Only
        Documents and Links

Page types
----------

Wagtail offers a different form depending on where in the tree you are adding
a page:

``Standard page``
    The workhorse: a title, a short intro and a body you build out of blocks.
    Use it for anything that is not news, a DART or the contact page.

``News index`` / ``News post``
    The index lists the posts below it, newest first, eight to a page.  A post
    has a date, an intro, an optional lead image and a body.

``DART index`` / ``DART page``
    The index renders the teams as a table — name, airport, city, leader.  A
    DART page links to the DART record members can join, so the airport
    identifier and city come from the membership database rather than being
    retyped.

``Contact page``
    An intro plus the contact details, which are pulled from Site Settings so
    the address is only ever maintained in one place.

``Home page``
    There is exactly one, and it is the root of the site.  It has a hero, a
    mission statement, a numbered "concept of operations" and a tax-status
    note, and it lists the three most recent news posts automatically.


Creating, editing and publishing
================================

Add a page
----------

#. **Pages** → navigate to the page that should be the parent.
#. Choose **Add child page** and pick the page type.
#. Fill in the title.  Wagtail proposes a URL slug from it; you can change the
   slug under the **Promote** tab, but changing it later breaks existing links.
#. Write the intro and build the body (see :ref:`blocks`).
#. **Save draft** while you work, then **Preview** to see it as a visitor
   would.
#. **Publish** when it is ready.

Edit a page
-----------

Click the page title in the tree, or hover over it and choose **Edit**.  Every
save creates a revision, so you can compare and roll back from the **History**
view; nothing you do here is unrecoverable.

Choosing **Save draft** on a live page leaves the published version alone and
keeps your changes as a draft — the tree marks the page with an unpublished
changes badge until you publish.

Reorder pages
-------------

In the parent page's listing, choose the **Sort** (arrows) control and drag the
children into the order you want.  The order affects the navigation and any
index page.

Unpublish and delete
--------------------

**Unpublish** takes a page off the public site and out of the menu but keeps it
in the tree, ready to publish again.  Prefer it to deleting.

**Delete** removes the page and every page underneath it.  Wagtail asks for
confirmation and tells you how many descendants will go.  Deleting is the only
action here you cannot undo from the History view, so unpublish first and
delete later if you are unsure.

Show a page in the top navigation
---------------------------------

Only *top-level* pages — the direct children of Home — appear in the main
menu, and only when **Show in menus** is ticked on the **Promote** tab.  Two
entries are always present and are not pages: **Join**, which goes to the
sign-up flow, and **Log in** / **Members**, which goes to the member portal.

Deeper pages are reached from their parent, which lists its children in the
"In this section" panel automatically.


.. _blocks:

Building a body out of blocks
=============================

Page bodies are made of blocks.  Choose the **+** button to insert one, drag
the handle to reorder, and use the block menu to duplicate or delete.

=================  ==========================================================
Block              What it is for
=================  ==========================================================
Heading            A section heading.  H2 headings also become the "on this
                   page" list on long pages, so use them for real sections
                   and H3 for sub-points.
Paragraph          Rich text: bold, italic, links, bullet and numbered lists,
                   quotes, horizontal rules, H3 and H4.
Image              An uploaded image with optional caption and credit.  Fill
                   in the alt text unless the image is purely decorative.
Quote              A pull-quote, with an optional attribution.
Call to action     A button.  Point it at a page in the tree *or* type a URL
                   such as ``/portal/join``.  The optional note prints as
                   small print underneath.
Document           A link to an uploaded file, with its type and size shown.
Two columns        Two side-by-side stacks of the blocks above; they stack
                   on a phone.
Embed              Paste a YouTube or Vimeo URL and the player is embedded.
Raw HTML           Unescaped HTML.  Only offered to website administrators,
                   because bad markup here can break the page.
=================  ==========================================================

Write in sentences, keep paragraphs short, and let the design system do the
styling — there is no need to reach for Raw HTML to make something look right.


Images and documents
====================

**Images** in the left-hand menu is the image library.  Upload once and reuse
anywhere; Wagtail generates the sizes each template needs.  JPEG, PNG, WebP,
GIF and SVG are accepted.

**Documents** is the same idea for files people download: PDF, DOCX, XLSX,
PPTX, CSV, TXT, RTF, ODT, Keynote and ZIP.  Link to them with the Document
block, or from rich text with the document-link button.

Give every upload a title that describes it — the title is what appears in the
chooser, in search, and (for documents) as the default link text.


The members-only area
=====================

Standard pages and news posts have a **Members only** switch.  Turn it on and
the page is served only to:

* signed-in members whose membership is current, and
* DART leaders, account, user, website and system administrators.

Everyone else gets a wall instead of the content, with the one action that
would fix it for them: sign in, renew, or join.  Search engines never see the
content, and members-only news posts are hidden from the news index for
visitors who could not open them.

The switch is per page.  Turning it on for "Members" does **not** close the
pages underneath it, so set it on each page you want closed.

.. tip::

   Wagtail's own **Privacy** setting (on the page's ellipsis menu) still
   works, and can restrict a page by password or by Wagtail group.  The
   members-only switch is the one to use for "current members only" because it
   understands membership expiry.


Site settings
=============

**Settings → Site settings** holds the details that appear on every page:

=====================  ======================================================
Field                  Where it shows
=====================  ======================================================
Organisation name      Page titles, footer, the member portal
Tagline                Under the wordmark, and as the default page
                       description for search engines
EIN                    Footer and the contact page
Contact email          Footer, contact page, the members-only wall
Contact phone          Footer and contact page
Mailing address        Footer and contact page
Donate URL             Footer link
Facebook / X URL       Footer links
Theme                  The whole colour palette — see below
Footer text            The small print in the first footer column
=====================  ======================================================

Changing the theme
------------------

**Theme** offers the palettes shipped with the site:

``Sierra``
    The default.  Warm paper, deep conifer green, signal orange.

``Pacific``
    Cooler paper and a deep blue primary.

``Night``
    A dark palette.

Saving a new theme changes the public site *and* the member portal
immediately, so the two always match.

To see a theme before you commit to it, add ``?theme=`` to any page's URL
while you are signed in as a website or system administrator — for example
``https://<your-site>/about/?theme=night``.  The preview is yours alone: it
changes nothing on the server and nobody else sees it.

Adding a fourth theme is a developer task; see :doc:`../developer/theming`.


Things worth knowing
====================

* **Changing a slug changes the URL.**  Old links, printed flyers and search
  results will 404.  If you must, ask a developer to add a redirect —
  Wagtail's **Redirects** tool is in the left-hand menu.
* **The home page's news list is automatic.**  Publish a news post and it
  appears; there is nothing to update by hand.
* **DART pages read the airport and city from the membership database.**  If
  they are wrong, an account administrator fixes the DART record, not the
  page.
* **Preview before you publish**, especially on a phone-width window: the
  design is built mobile-first and long headings behave differently there.
