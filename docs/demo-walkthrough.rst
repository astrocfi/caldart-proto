================
Demo walkthrough
================

This page drives the whole prototype in about twenty minutes, using the demo
data ``make seed`` creates.  It follows the five flows the system exists for
in order, and each one builds on the last: the profile you
edit in flow B is the record the DART leader reads in flow C, and the payment
you make in flow A is the one that shows up in the account administrator's
month column in flow D.

Nothing here charges money.  With no Stripe or PayPal keys configured the
checkout offers only the **mock** provider, which has a *Succeed* button and a
*Fail* button and talks to nothing outside your machine.

Prerequisites
=============

Bring the application up as :doc:`developer/setup` describes:

.. code-block:: console

   $ make setup
   $ make up
   $ make migrate
   $ make seed
   $ make build
   $ make run

``make run`` serves the site on http://localhost:8000/.  Leave Mailpit's inbox
at http://localhost:8025/ open in a second tab — every email the system sends
in development lands there and nowhere else.

.. note::

   If you run several checkouts of this repository side by side, each one uses
   its own database, but ``make run`` always serves on ``:8000``, so only one
   checkout can run at a time.

The demo accounts all use the password ``caldart-demo``:

.. list-table::
   :header-rows: 1
   :widths: 34 22 44

   * - Email
     - Name
     - Roles and state
   * - ``member@example.org``
     - Marta Reyes
     - ``member``; membership current
   * - ``expired@example.org``
     - Owen Delgado
     - ``member``; membership expired
   * - ``leader@example.org``
     - Priya Raman
     - ``member``, ``dart_leader``; current
   * - ``useradmin@example.org``
     - Nina Kowalski
     - ``member``, ``user_admin``; current
   * - ``treasurer@example.org``
     - Lucia Ferreira
     - ``member``, ``treasurer``; no membership term
   * - ``accountadmin@example.org``
     - Curtis Whitfield
     - ``member``, ``account_admin``; lifetime
   * - ``webadmin@example.org``
     - Ada Lindqvist
     - ``member``, ``website_admin``; current
   * - ``sysadmin@example.org``
     - Rafael Ibarra
     - ``member``, ``system_admin``, Django superuser; lifetime

Alongside them the seed creates about forty generated members with mixed
membership, certificate, and medical states, twenty-five aircraft with varied
insurance currency, and two years of payment history.  The generated data comes
from a fixed random seed, so the same names appear on every machine; their
dates are relative to the day you seeded, so a *"expires in 40 days"* stays
true whenever you run it.

Sign out between flows.  Each one starts from a different person, and the
portal deliberately clears its cache on sign-out so no screen can show you the
previous user's data.

.. _walkthrough-flow-a:

Flow A — a visitor joins and pays
=================================

*Goal: somebody who has never heard of CalDART becomes a current member
without leaving the site, and the membership is live the moment the payment
clears.*

1. Open http://localhost:8000/ signed out.  You get the public home page:
   the welcome box with its photograph and mission statement, the three most
   recent news posts, and the missions CalDART has flown.
2. Follow **Join** in the top navigation — the button on the right-hand side,
   not the *Join CalDART* content page beside it.  You land on
   ``/portal/join`` at step 1 of 5, **Account**.
3. Fill in a first name, a last name, an email address that is not already in
   use, and a password.  Choose something that is not obviously derived from
   the name you just typed: the password is checked against Django's
   validators *with the new account's own details*, so ``marta-reyes-2026``
   for a Marta Reyes is refused.  Submit.

   You are now signed in.  The wizard advances to step 2, **Verify**, and
   waits.  Open Mailpit at http://localhost:8025, open the *verify your email
   address* message, and follow its link.  The page says **Email verified**;
   press **Continue** and the wizard moves on to step 3, **Profile**.

4. Fill in the profile.  Phone, street address, city, and ZIP code are what the
   form insists on, along with the certificate box, which always holds a value
   — *Not a pilot* counts.  Everything else — DART, home airport, certificate
   number, medical, ratings, hours, volunteer interests — is optional but is
   what makes the rest of the system useful.  Pick a DART from the list; it is
   populated from ``GET /api/v1/darts``.

   If you enter a medical class you must also enter its expiry date, and if
   you enter a certificate type you must also give the certificate number.
   The form says so inline rather than at submit time.

5. Step 4, **Pay**.  Choose **Annual** ($45.00) or **Life** ($650.00), then a
   contribution if you want one — the tiers run from *Participating* at $20 to
   *Platinum* at $10,000, with an *Other amount* box and a *No thank you*.
   The total updates as you choose.

   Below the plan is one tab per configured payment provider.  With no keys
   set the only tab is **Test payment**.  Press **Succeed**.

   .. tip::

      Press **Fail** first if you want to see the failure path.  You get *"The
      test payment was declined. Nothing was charged."* and stay on the step
      with your choices intact.  Nothing is written except a ``Payment`` row
      with status ``failed``.

6. Step 5, **Done**.  The membership is already active — the server activated
   the term inside the same request that recorded the payment, not on a
   webhook or a nightly job.  The page links on to the dashboard and to the
   members-only pages.

**What success looks like.**  Go to ``/portal/`` and the membership card reads
**Current** with an expiry date 364 days after today for the Annual plan
(``starts_on + duration_days - 1``), or **Lifetime** with no date for Life.
The public page ``/members/`` now opens instead of showing the wall.

.. _walkthrough-flow-b:

Flow B — a member signs in, edits their profile, reads members-only content
===========================================================================

*Goal: an existing member keeps their own record current and gets at what
membership buys.*

1. Sign out, then sign in at ``/portal/login`` as ``member@example.org`` /
   ``caldart-demo``.  You arrive at the dashboard: a membership status chip
   with the expiry date, a renewal call to action, quick links filtered to
   your roles, the members-only pages, and your recent payments.

   Marta's seeded profile has no certificate and no medical on file, which is
   what makes her interesting for flow C.  We are about to fix that.

2. Go to **My profile**.  The form is in three sections — Contact, Aviation,
   Volunteer interests — one column on a phone and two from about 40rem wide.
3. In *Aviation*, set **Pilot certificate** to ``Private`` and type any
   certificate number; set **Medical** to ``Third class`` and give an
   expiration date comfortably in the future; set **IFR rated** as you like.
   Save.  A toast confirms it.

   Try saving with the medical class set but the expiry blank: the field is
   marked and the save is refused.  The same rule is enforced on the server,
   so an API client cannot store a medical without its date either.

4. Go to **My aircraft**.  Search the register — type ``N419JM``, or any part
   of a make or model such as ``Cirrus``.  The picker looks the exact
   registration up first and falls back to a fuzzy search, so ``419jm``
   , ``n-419jm``, and ``N419JM`` all find the same airplane.

   Each result carries an insurance chip.  Pick one whose chip says
   **Current** and add it.  It appears in your list with the same chip and a
   *Remove* button.

   If the airplane you fly is not in the register, the picker offers a short
   inline form to add it — make, model, and the insurance details — and selects
   it for you.  You may edit an aircraft you added; only an account
   administrator may edit one somebody else added.

5. Read members-only content.  From the dashboard, follow one of the
   members-only page links, or open http://localhost:8000/members/ directly.
   It renders because your membership is current.

**What success looks like.**  Sign out and open
http://localhost:8000/members/ again: you get the members-only wall with HTTP
403 and a *sign in* call to action.  Sign in as ``expired@example.org`` and
the same page offers *renew* instead, naming the date the membership ran out.

.. _walkthrough-flow-c:

Flow C — a DART leader checks a member before a flight
======================================================

*Goal: standing on a ramp with a phone, answer "may this person fly this
airplane for us today?" in one screen.*

1. Sign out and sign in as ``leader@example.org`` / ``caldart-demo``.
2. Follow **Member check** in the Operations group of the navigation
   (``/portal/leader``).
3. Search for ``Reyes``.  Search covers name in either word order, email
   address and N-number; the N-number branch only runs when your term contains
   a digit, so searching for *Nate* does not match every US registration on
   file.
4. Choose Marta Reyes from the results.  The status card opens.

   Across the top is a full-width verdict band that says **GO** or **NO-GO**
   in words as well as color.  Because you gave Marta a current medical in
   flow B, and her membership is current, the verdict is **GO** — *"Membership
   and medical are current"*.

   Below it, one row each for:

   - **Membership** — current, expired, or none, with the expiry date and plan.
   - **Medical** — the class and expiry, and whether it is current.  BasicMed
     and class medicals both use the stored expiration date.
   - **Certificate** — type, number, IFR rating and any ratings on file.
   - **Aircraft** — a row per airplane attached to the profile, each with its
     own insurance state, limits, and expiry.

   The verdict is membership **and** medical.  Insurance is shown per
   airplane rather than folded into the verdict, because which airplane the
   member is about to fly is a fact you have and the system does not.

5. Undo flow B's edit if you want to see the other outcome: clear Marta's
   medical, or check a member who has a lapsed one.  The band turns **NO-GO**
   and states the reasons — *"Medical expired"*, *"Membership expired"* —
   in the order a leader would say them out loud.
6. Follow **Aircraft check** (``/portal/leader/aircraft``), type a
   registration, e.g. ``N419JM``, and tap the result.  You get the airplane's
   insurance card and a list of the members who fly it, each with their own
   membership and medical currency.

**What success looks like.**  The subject of the card is in the query string,
so a card can be reloaded, backed out of, or sent to another leader as a link.

.. _walkthrough-flow-d:

Flow D — an account administrator reviews payments by month and year
====================================================================

*Goal: "what did we take in March, and how does this year compare?"*

1. Sign out and sign in as ``accountadmin@example.org`` / ``caldart-demo``.
2. Follow **Payments** in the Administration group (``/portal/admin/payments``).
3. Three tiles across the top give **This month**, **Year to date** and **Last
   12 months**.  The mock payment you made in flow A is in all three.
4. Below them, switch the table between **Month** and **Year**.  Each row is a
   period with the number of payments, the total, the split between plan money
   and contributions, and a column per provider.  The seed lays down two years
   of history, so both views have something to show.
5. Under that is every payment, one row each, with a filter bar: a date range,
   provider, status, and a free-text search.  Sorting and paging both go to the
   server, so they are consistent across pages rather than sorting only what
   is on screen.
6. Press **Export CSV**.  The download carries whatever filters the screen is
   showing — narrow the date range first and the file narrows with it.

**What success looks like.**  The tiles, the period table and the export all
key off one "when was this paid" rule — ``completed_at`` when the payment
succeeded, and the creation time otherwise — so the three never disagree.

While you are signed in as this administrator, look at the other two
Administration screens as well: **Members** (``/portal/admin/members``) with
the full filter set — status, certificate, medical, DART, role, *expiring
within N days* — and its CSV and PDF exports, and **Aircraft**
(``/portal/admin/aircraft``) with the insurance filters and the same pair of
exports.  Both are covered in :doc:`user/account-administrator-guide`.

.. _walkthrough-flow-e:

Flow E — a website administrator adds, edits, and deletes a page
================================================================

*Goal: change the public site without touching the code.*

1. Sign out and sign in to the Wagtail admin at
   http://localhost:8000/admin/ as ``webadmin@example.org`` /
   ``caldart-demo``.  Wagtail has its own login form but shares the portal's
   session and the same account, so signing in to ``/portal/`` first would
   have let you straight in.  What decides the matter is the ``website_admin``
   role: sign in as ``member@example.org`` and ``/admin/`` bounces you back to
   the login form.
2. Open **Pages** and walk down to *Home*.  The tree is: Home; About Us with
   History, the DART directory and its sixteen team pages, and Directors and
   Officers; News with three posts; Join CalDART; Donate; Sponsors; Contact
   Us; and a members-only Members section.
3. **Add a page.**  Under *Home*, choose **Add child page** and pick
   **Standard page**.  Give it a title and an intro, then build the body out
   of blocks: heading, paragraph, image, quote, call to action, document,
   two columns, embed.  Save as draft, then **Publish**.

   Visit the URL Wagtail shows you.  The page renders in the site's style with
   an "on this page" rail built from your heading blocks.

4. **Make it members-only.**  Edit the page, open the **Access** panel and
   tick *members only*, then publish.  Sign out and visit the page: you get
   the wall and HTTP 403.  Sign in as ``member@example.org`` and it opens.
5. **Show it in the navigation.**  Edit the page, open the **Promote** tab and
   tick *Show in menus*.  The top navigation picks it up on the next request.
6. **Reorder, unpublish, delete.**  Drag pages in the explorer to reorder
   them; *Unpublish* takes a page off the site while keeping its content;
   *Delete* removes it for good.  Delete the page you made.
7. **Site settings.**  Open **Settings → Site settings**: organization name,
   tagline, contact email and phone, mailing address, EIN, donate URL, social
   links, footer text — and **theme**.  Switch the theme to ``pacific`` or
   ``night``, save, and reload the public site.

   You can preview a theme without committing to it by adding
   ``?theme=night`` to any public URL; only website and system administrators
   are allowed to.

**What success looks like.**  You are deliberately *not* a Django superuser.
You can edit pages, images, documents, redirects, and site settings.
``website_admin`` also sets the Django ``is_staff`` flag, so you can sign in to
``/django-admin/`` too — its index comes up empty, because you hold no Django
model permissions there.  The portal's own system screens stay out of reach:
those need the ``system_admin`` role.

After the walkthrough
=====================

Two more screens are worth a look, neither of them one of the five flows:

**Users and roles** — sign in as ``useradmin@example.org`` and open
``/portal/admin/users``.  Search for a member, open them, and add or remove
roles; press *Send password reset* and watch the email arrive in Mailpit.  See
:doc:`user/user-administrator`.

**System** — sign in as ``sysadmin@example.org`` and open ``/portal/system``.
Health shows database connectivity, pending migrations, free disk and the last
backup; Backups lists the dumps in ``backups/`` and can make a new one;
Reminders runs the renewal scan — leave *dry run* ticked the first time — and
lists what was recently sent.  Then try the scan from the command line against
a future date, which is how you rehearse a year's worth of reminders in a
second:

.. code-block:: console

   $ make reminders TODAY=2027-01-01 DRY_RUN=1

The Renewals panel runs the automatic-renewal scan: the seed leaves two
members with an ordinary renewal due today and one with a catch-up renewal
overdue, so a dry run there reports three charges and a real run makes them.

See :doc:`user/system-administrator-guide` and
:doc:`developer/reminders`.

The seed also leaves three report subscriptions and every DART's roster due
the day it runs, so ``uv run backend/manage.py send_scheduled_reports`` always
has real mail to send; see :doc:`developer/scheduled-reports`.

When you are finished, stop Django with :kbd:`Ctrl-C`.  Leave the containers
running, or stop them with ``make down`` — the data survives in the
``caldart_pgdata`` volume either way.

Troubleshooting
===============

.. rubric:: Flow A — a visitor joins and pays

- *"An account already uses that email address. Sign in, or reset your
  password."*  Case-insensitive: registering ``Marta@example.org`` collides
  with ``marta@example.org``.
- *The provider tab list is empty.*  ``PAYMENTS_MOCK_ENABLED`` is off and no
  Stripe or PayPal keys are configured.  See
  :doc:`developer/payments-setup`.
- *You closed the tab mid-wizard.*  Return to ``/portal/join`` and it resumes
  at the furthest step you actually finished — the wizard derives that from
  the server's view of you (session, then ``profile_complete``, then
  membership), not from anything stored in the browser.  You may go back to
  an earlier step; you cannot skip ahead.

.. rubric:: Flow B — a member signs in, edits their profile, reads
   members-only content

- *"A phone number is required."*  The portal's form asks for phone, street
  address, city, and ZIP code, plus the certificate box, which always holds a
  value — the same list the server uses for ``profile_complete``.  The API
  itself only insists on phone, so a client that is not the portal may store a
  partial profile.
- *The "finish your profile" nudge will not go away.*  It reads
  ``profile_complete``; open **Profile** and fill in whichever of those fields
  is still blank.
- *An aircraft will not attach.*  Attaching is idempotent, so a second attempt
  at the same airplane is silently fine; a genuinely unknown id is a 404.
- *You cannot see a members-only page you expect to see.*  Membership status
  is not the only gate: any role beyond plain ``member`` also gets through.  A
  DART leader with no membership of their own can read members-only pages.

.. rubric:: Flow C — a DART leader checks a member before a flight

- *"Nobody matches that."*  Search is over name, email, phone number, and
  N-number.  A certificate number will not find anybody here — that is the
  account administrator's search field.
- *A member with no profile at all.*  You get a well-formed NO-GO card rather
  than an error.
- *An airplane marked out of service* is labeled as such on the card, and is
  dropped from the picker's fuzzy search — though an exact registration still
  finds it, labeled, so nobody adds a duplicate.

.. rubric:: Flow D — an account administrator reviews payments by month
   and year

- *"No payments match these filters."*  The default range is not "all time".
  Widen the dates or clear the filters.
- *The provider column you want is empty.*  Only providers that were actually
  configured when a payment was taken appear against it; a demo database has
  everything under ``mock``.

.. rubric:: Flow E — a website administrator adds, edits, and deletes a page

- *The raw HTML block is missing from your block picker.*  It is restricted to
  ``website_admin`` and ``system_admin``; the block list is rebuilt per editing
  user, so someone with fewer permissions simply does not see it.
- *A page will not go where you want it.*  Page types constrain the tree — a
  news post may only live under the news index, a DART page only under the
  DART directory.
- *Your changes to Site settings vanished after a re-seed.*  They should not:
  ``seed_content`` only fills in settings that are still blank.  It does
  replace page content, so make example edits on a page you added.

Related material
================

- :doc:`/developer/setup` — bring the application up from a clean checkout.
- :doc:`/developer/payments-setup` — configure Stripe or PayPal instead of the
  mock provider.
- :doc:`/user/account-administrator-guide` — the full member, aircraft, and
  payment filters and exports.
- :doc:`/user/user-administrator` — manage accounts and roles.
- :doc:`/user/system-administrator-guide` — health, backups, and reminders from
  the portal.
- :doc:`/developer/reminders` — how the renewal scan decides what to send.
