===========================
Website administrator guide
===========================

This guide is for people who hold the ``website_admin`` role: you look after
the public |org| website — the pages, their words and pictures, the members-only
area, and the organization details that appear in the header and footer.

You do not need to know anything about the member database, payments, or
reports.  Those live in the member portal and belong to other roles.


Signing in
==========

The content management system is Wagtail, and it lives at ``/admin/``:

* production: ``https://<your-site>/admin/``
* local development: ``http://localhost:8000/admin/``

Sign in with the same email address and password you use for the member
portal — it is the same account and the same session, so if you are already
signed in to the portal, ``/admin/`` opens without asking again.  If Wagtail
sends you back to the login form instead, your account is missing the
``website_admin`` role — ask a user administrator to add it.

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
        How It Works
        History
        DARTs                       one page per team
        Directors and Officers
      News                          the index; posts live under it
      Events                        the calendar; events live under it
      Join CalDART
      Donate
      Sponsors
      Contact Us
      Members Only                  members only
        Notices
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

``Event index`` / ``Event``
    The calendar. An event has a date, the time it runs ("9 am to 1 pm"), where
    it is, a one-line intro for the listing, and a body for the details. The
    index lists everything still ahead in full, then what has already happened,
    twenty to a page. The home page's sidebar picks up the three soonest by
    itself.

``DART index`` / ``DART page``
    The index renders the teams as a table — name, airport, leader.  A
    DART page links to the DART record members can join, so the airport
    identifier and city come from the membership database rather than being
    retyped.

``Contact page``
    An intro plus the contact details, which are pulled from Site Settings so
    the address is only ever maintained in one place.

``Home page``
    There is exactly one, and it is the root of the site.  Its welcome box
    holds a photograph, a standfirst, the mission statement, the paragraphs
    below it and three buttons, the first of which is the red one asking for
    air support.  Below that it lists the three most recent news posts
    automatically, then the missions CalDART has flown, which you write as
    year-and-description blocks.  The sidebar picks up the three soonest
    events from the calendar by itself, and an event whose date has passed
    drops off it.  The tax-status note is shown in the membership box below
    them.


Putting an event on the calendar
--------------------------------

#. Open **Pages**, then **Events**, and choose **Add child page**.
#. Give it a title — what people will see in the sidebar and on the calendar.
#. Fill in the **Event date**. That date alone decides where the event
   appears: today or later puts it under *Coming up* and in the home page's
   sidebar, and yesterday or earlier moves it to *Already happened*. Nothing
   has to be tidied away afterwards.
#. **Time** and **Location** are free text and both optional: "9 am to 1 pm"
   and "Reid-Hillview (KRHV)" read together as one line.
#. **Intro** is the one line shown in the calendar listing; the **Body** is
   everything else, built from the same blocks as any other page.
#. **Publish**. A draft is invisible until you do.

To correct an event, open it and publish again. To take one down, unpublish
it: deleting is only worth it for something posted by mistake, since a past
event is a record of what the network did.


Creating, editing, and publishing
=================================

Add a page
----------

#. **Pages** → navigate to the page that should be the parent.
#. Choose **Add child page** and pick the page type.
#. Fill in the title.  Wagtail proposes a URL slug from it; you can change the
   slug under the **Promote** tab.  Changing it later changes the page's URL,
   and Wagtail redirects the old one for you once you publish the change (see
   :ref:`redirects`).
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

The bar opens with **Home**, which is always there and is not a page you
edit.  After it come the *top-level* pages — the direct children of Home —
that have **Show in menus** ticked on their **Promote** tab.  A page with
in-menu children of its own gets a drop-down listing them, which is how
About Us offers History, DARTs, Directors and Officers, and Sponsors.

Two things sit at the right-hand end: any menu page behind the members-only
wall, and **Sign in** / **Member portal**, which is not a page either.  A
signed-in reader is greeted there by first name.

Deeper pages are still reached from their parent, which lists its children in
the "In this section" panel automatically.


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
Paragraph          Rich text: bold, italic, links, bullet, and numbered lists,
                   quotes, horizontal rules, H3, and H4.
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
anywhere; Wagtail generates the sizes each template needs.  JPEG, PNG, WebP
, GIF, and SVG are accepted.

**Documents** is the same idea for files people download: PDF, DOCX, XLSX,
PPTX, CSV, TXT, RTF, ODT, Keynote, and ZIP.  Link to them with the Document
block, or from rich text with the document-link button.

Give every upload a title that describes it — the title is what appears in the
chooser, in search, and (for documents) as the default link text.

Every document belongs to a **collection**, chosen when you upload it and
changeable afterwards on the document's own page.  The collection is what
decides who may download the file: see :ref:`members-only-documents` below.


The members-only area
=====================

Standard pages and news posts have a **Members only** switch.  Turn it on and
the page is served only to:

* signed-in members whose membership is current, and
* DART leaders, account, user, website, and system administrators.

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


.. _members-only-documents:

Members-only documents
----------------------

The switch closes a *page*.  A file is closed by the collection it lives in:
upload it into the **Members only** collection, and it is served to exactly the
people the switch lets through.  Everyone else gets the same wall, with HTTP
403, instead of the file — whether they followed a link or typed the URL.

Collections nest, so you can group the files without opening them up: anything
under **Members only**, such as a "Board minutes" collection inside it, is
closed too.

Files in any other collection — the root collection a document lands in by
default, a "Press kit" collection, anything else — are public to anyone with
the link.  Put the handbooks, rosters, bylaws, and member forms in **Members
only**, and leave flyers, logos, and public forms outside it.

To move a file that is already uploaded, open it under **Documents**, change
**Collection** and save; the links to it keep working.

.. note::

   The **Documents** list has a collection filter; use it to check what sits in
   **Members only**.  When you upload several files at once, the collection you
   pick applies to the whole batch, so upload members-only files separately
   from public ones.


Site settings
=============

**Settings → Site settings** holds the details that appear on every page:

=====================  ======================================================
Field                  Where it shows
=====================  ======================================================
Org name               Page titles, footer, the member portal
Tagline                Under the logo, and as the default page
                       description for search engines
EIN                    Footer and the contact page
Contact email          Footer, contact page, the members-only wall
Duty officer phone     The masthead, the footer and the contact page.  It is
                       the only number the site publishes
Mailing address        Masthead, footer, and contact page
Donate url             Footer link
Facebook url           Footer link
Twitter url            Footer link
Theme                  The whole color palette — see below
Footer text            The small print in the first footer column
=====================  ======================================================

Changing the theme
------------------

**Theme** offers the fourteen looks shipped with the site.  Each one changes
the palette *and* the typefaces:

``Duty (default, blue and red)``
    A blue-gray ground, a white page panel, navy chrome and the wordmark's red
    for the one urgent button.

``Sierra (warm paper)``
    Warm paper, deep conifer green, signal orange.

``Pacific (cool paper)``
    Cooler paper and a deep blue primary.

``Night (dark)``
    A dark palette.

``Squadron (logo blue on white)``
    The CalDART logo colors on white: cobalt, crimson and a lot of air.

``Flight deck (logo blue, dark)``
    The same logo colors on a deep navy instrument panel.

``Contrail (logo blue, sky paper)``
    The logo colors on pale sky paper; light and airy.

``Sectional (aeronautical chart)``
    Chart cream, chart blue, airspace magenta and terrain tan.

``Tarmac (concrete and asphalt)``
    Industrial neutrals with safety yellow used on surfaces only.

``Coastal (fog and ocean teal)``
    Fog paper, ocean teal, sunset coral and dune sand.

``Slate (cool corporate)``
    Slate blue-gray with amber emphasis.

``Meridian (high-contrast civic)``
    White, navy and burnt orange, with one typeface throughout.

``Monterey night (charcoal dark)``
    A charcoal dark palette with a sea-green primary and amber accent.

``Granite (near-monochrome)``
    White, near-black and grays, with one blue for links.

Every theme meets the same contrast standard, so no choice makes the site
harder to read.  Saving a new theme changes the public site *and* the member
portal immediately, so the two always match.

To see a theme before you commit to it, add ``?theme=`` to any page's URL
while you are signed in as a website or system administrator — for example
``https://<your-site>/about/?theme=night``.  The preview is yours alone: it
changes nothing on the server and nobody else sees it.

Adding another theme is a developer task; see :doc:`/developer/theming`.


.. _redirects:

Redirects
=========

**Settings → Redirects** lists every address the site forwards somewhere else.
The table has four columns: **From** (the old path), **Site**, **To** (the
page or URL it lands on) and **Type**, which is *Permanent* or *Temporary*.

Most rows arrive on their own.  When you publish a slug change, or move a page
to a different parent, Wagtail writes a redirect from the page's old URL —
and from the old URL of every page beneath it — to the address each one has
now.  That is why renaming a page is safe: the printed flyer with the old
address still works.

To add one by hand, press **Add redirect** and fill in:

**Redirect from**
   The old path, such as ``/old-news``.

**From site**
   Leave it as it is unless the site serves more than one hostname.

**Permanent**
   Ticked by default, which answers a 301.  Untick it for a redirect you
   intend to remove, which answers a 302.

**Redirect to a page** or **Redirect to any URL**
   Choose a page from the tree, or type an address.  Use one or the other, not
   both.

You may add, change, and delete redirects; the role grants all three.  Deleting
one that Wagtail created restores the 404, so remove a redirect only when you
want the old address to stop working.


Things worth knowing
====================

* **Changing a slug changes the URL.**  When you publish the change, Wagtail
  adds a redirect from the old address automatically, so existing links keep
  working.  **Settings → Redirects** lists those redirects, and you can add
  , change, or delete your own there (see :ref:`redirects`).
* **The home page's news list is automatic.**  Publish a news post and it
  appears; there is nothing to update by hand.
* **DART pages read the airport and city from the membership database.**  If
  they are wrong, an account administrator fixes the DART record, not the
  page.
* **Preview before you publish**, especially on a phone-width window: the
  design is built mobile-first and long headings behave differently there.


When something goes wrong
=========================

**You cannot get into** ``/admin/``.
   It is the role, not the password.  Wagtail shares the portal's session, so
   if you are already signed in to ``/portal/`` and ``/admin/`` still bounces
   you to a login form, your account is missing ``website_admin`` — ask a user
   administrator to add it.

**The page type you want is not offered.**
   The tree constrains itself on purpose: a news post may only be added under
   the news index, and a DART page only under the DART directory.  Add the
   child from the right parent and the type appears.

**The raw HTML block is missing from the block picker.**
   It is restricted to website and system administrators.  The block list is
   rebuilt for the person editing, so somebody without the role simply does
   not see it — nothing is broken.

**Your edits are not on the live site.**
   Saving a draft is not publishing.  Open the page and use **Publish**; the
   explorer marks pages that have unpublished changes.

**A page you published is not in the top navigation.**
   The menu is built from pages with **Show in menus** ticked, which lives on
   the **Promote** tab, not on the content tab.

**A page 404s that used to work.**
   Its slug changed, which changes its URL.  Open **Settings → Redirects** and
   use **Add redirect** to point the old path at the page.  Setting the slug
   back works too.  A slug change you published should have created the
   redirect for you, so check the list before you add one by hand.

**A members-only page shows the wall to you as well.**
   Only while you are signed out of the *portal*.  Signed in, any role beyond
   plain ``member`` gets through whatever your own membership is doing.

**A DART page shows the wrong airport.**
   It is read from the membership database, not typed on the page.  An
   account administrator corrects the DART record and every page follows.

**Your Site settings edits disappeared after a re-seed.**
   They should not — ``seed_content`` only fills in settings that are still
   blank, so a theme or a contact address you chose survives.  Page *content*
   is a different matter: the seeded pages are rewritten, so make your own
   changes on pages you added.

**An image or document will not upload.**
   The allowed types are fixed: images as GIF, JPEG, PNG, WebP, or SVG, and
   documents as CSV, DOCX, KEY, ODT, PDF, PPTX, RTF, TXT, XLSX, or ZIP.  On the
   live site there is also a 25 MB size cap.  Photographs straight off a
   camera are usually far larger than a web page needs — resize before
   uploading and the site will be quicker as well.
