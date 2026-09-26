================
Pages and blocks
================

Everything on the public website is a page, and every page hangs off the home page. This
page explains how the tree of pages is arranged, how to add, edit, publish, and take
down a page, and how to build a page's body out of blocks.

What you see
============

The page tree
~~~~~~~~~~~~~

Choose **Pages** in the editor's left-hand menu to walk the tree. The site starts out
like this:

* **Home**

  * **About Us**, with **How It Works**, **History**, **DARTs** (one page beneath it
    for each Disaster Airlift Response Team, or DART, a local team at a general aviation
    airport), **Directors and Officers**, and **Sponsors**
  * **News**, with the news posts beneath it
  * **Events**, with the events beneath it
  * **Join CalDART**
  * **Donate**
  * **Contact Us**
  * **Members Only**, with **Notices** and **Documents and Links**

Each page in the list has a menu with **Edit**, **View live**, **Add child page**,
**Move**, **Copy**, **Delete**, **Unpublish**, and **History**.

Page types
~~~~~~~~~~

When you choose **Add child page**, the editor offers only the types that belong under
that parent. Under **Home** and under a standard page it offers:

* **Standard page**, the everyday page: a title, a one- or two-sentence **Intro**, and a
  **Body** built from blocks. Use it for anything that is not news, an event, a DART, the
  contact page, or the donation page.
* **News index**, a list of news posts (see :doc:`news-and-events`).
* **DART index**, the directory of teams (see :doc:`dart-pages`).
* **Contact page**, an **Intro** and a **Body**, with the phone number, email address,
  mailing address, and EIN shown beside them from the site settings (see
  :doc:`settings-and-themes`), so those details are only ever typed in one place.
* **Donate page**, the public donation page. Its **Intro** is shown above the donation
  form, and its **Thanks** replaces the form once a gift has gone through. The form
  itself is built in and needs no editing.

A news post can only be added under **News**, an event only under **Events**, and a DART
page only under **DARTs**. The **Events** calendar and the home page are set up with the
site; there is no type for adding another of either.

The home page
~~~~~~~~~~~~~

The home page has its own fields. The **Hero** group holds the welcome box: **Hero
heading**, **Hero lede**, **Hero image** and **Hero image caption**, and three buttons,
each a label and an address. The first, **Urgent cta label** and **Urgent cta url**, is
the red button asking for air support. The second, **Primary cta label** and **Primary
cta url**, starts out as **Join CalDART**. The third, **Secondary cta label** and
**Secondary cta url**, appears only when you give it a label. When the site settings
hold a **Donate url**, a **Donate** button sits beside them.

Below the buttons come **Mission statement** and **Welcome body**. The home page then
lists the three most recent news posts by itself. **Missions flown** holds a heading
(**Missions heading**, which starts as *Missions flown*) and a list of missions, each a
year and a line about what was flown. **Tax status** is the short note shown in the
**Membership** box in the sidebar.

The sidebar builds itself: **Upcoming events** (the three soonest), **Member sign-in**,
**Find your DART** (a list of the active teams that opens the chosen team's page), and
**Membership** (the plans and their prices).

What you can do
===============

Add a page
~~~~~~~~~~

#. In **Pages**, go to the page that should be the new page's parent.
#. Choose **Add child page**, and pick the page type.
#. Type the title. The editor makes the page's address (its **Slug**) from the title;
   you can change it on the **Promote** tab.
#. Write the intro and build the body (see below).
#. The editor keeps a draft as you work, and **Save draft** saves one at once. **Preview**
   shows the page as a visitor would see it.
#. Choose **Publish**, from the menu beside **Save draft**, when it is ready. A draft is
   invisible to visitors until you do.

Edit a page
~~~~~~~~~~~

Click the page's title in the tree, or choose **Edit** from its menu. Every save keeps a
revision, so **History** lets you compare versions and roll back. Changing a live page
and saving a draft leaves the published version in place, and the tree marks the page as
having unpublished changes until you publish.

Put a page in the top menu
~~~~~~~~~~~~~~~~~~~~~~~~~~

The top menu starts with **Home**, which is always there. After it come the pages
directly under Home that have **Show in menus** ticked on their **Promote** tab. A menu
page whose own children are ticked gets a drop-down listing them, which is how **About
Us** offers **How It Works**, **History**, **DARTs**, **Directors and Officers**, and
**Sponsors**. A members-only menu page moves to the right-hand end, beside **Sign in**
(or **Member portal** for a signed-in reader), which is not a page. Deeper pages are
reached from their parent, which lists its children in an **In this section** box.

Reorder pages
~~~~~~~~~~~~~

Choose **Sort menu order** on the parent and drag the children into order. The order
decides the menu and the order an index page lists its children in.

Unpublish or delete a page
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Unpublish** takes a page off the site and out of the menu, and keeps it in the tree
ready to publish again. Prefer it. **Delete** removes the page and every page beneath it,
after the editor tells you how many will go and asks you to confirm. It is the one
action **History** cannot undo, so unpublish first and delete later if you are unsure.

Build a body out of blocks
~~~~~~~~~~~~~~~~~~~~~~~~~~

A body is a stack of blocks. Choose **+** to add one, drag its handle to move it, and use
its menu to duplicate or delete it.

* **Heading**, a section heading. **Section (H2)** headings also make the **On this page**
  list, which appears once a page has three or more of them. **Sub-section (H3)** is for
  smaller points.
* **Paragraph**, text with bold, italic, links, links to documents, bulleted and numbered
  lists, quotes, dividing lines, and smaller headings.
* **Image**, a picture from the image library with an **Alt text** description, a
  **Caption**, a **Credit**, and **Full width** to let it run past the text. Fill in the
  alt text unless the picture is only decoration.
* **Quote**, a pull quote with an optional **Attribution**.
* **Call to action**, a button with a **Label**, a **Page** from the tree or a **Url**
  such as /portal/join, a **Style** (**Primary**, **Secondary**, or **Quiet**), and a
  **Note** printed small beneath it. Without a page or an address the editor says *Choose
  a page or enter a URL.*
* **Document**, a download link to a file from the document library, with a **Label**
  and a **Description** (see :doc:`redirects-and-documents`).
* **Two columns**, two side-by-side stacks of the blocks above, which stack on a phone.
* **Embed**, a YouTube or Vimeo address, shown as a player.
* **Raw HTML**, offered only to website and system administrators, because a mistake in
  it can break the page.

Write in short paragraphs and let the site's design do the styling. There is no need to
reach for **Raw HTML** to make something look right.

If something looks wrong
========================

If your edits are not on the live site, the page is still a draft: open it and choose
**Publish**. If a page you published is missing from the top menu, tick **Show in menus**
on its **Promote** tab. If the type you want is not offered, you are adding it under the
wrong parent: a news post goes under **News**, an event under **Events**, and a DART page
under **DARTs**. Preview on a phone-width window before publishing, since long headings
wrap differently there.
