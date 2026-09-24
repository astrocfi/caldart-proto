=======
CalDART
=======

CalDART is the website and member management system for |org|, a 501(c)(3)
that organizes California pilots and ground personnel to provide volunteer
disaster air transportation.

It is two things behind one address.  The **public website** — the home page,
the DART (Disaster Airlift Response Team) directory, the news, and the
members-only area — is managed in
Wagtail by the people who write the words.  The **member portal** at
``/portal/`` is a React application where members join, pay, renew, and keep
their own details current, DART leaders check whether somebody is fit to fly
before a mission, and administrators look after accounts, money, content, and
the machine it all runs on.

Where to start
==============

**If you use CalDART** — you are a member, a DART leader, or one of the
administrators — read the :doc:`user/index`.  Begin with
:doc:`user/getting-started`, which covers signing in and finding your way
around, then read the guide for what you do:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - You are
     - Read
   * - A member
     - :doc:`user/member-guide`, :doc:`user/payments`, :doc:`user/aircraft`
   * - A DART leader
     - :doc:`user/dart-leader-guide`
   * - A user administrator
     - :doc:`user/user-administrator`
   * - An account administrator
     - :doc:`user/account-administrator-guide`
   * - A website administrator
     - :doc:`user/website-administrator-guide`
   * - A system administrator
     - :doc:`user/system-administrator-guide`

**If you build CalDART**, read the :doc:`developer/index`.
:doc:`developer/setup` takes a clean machine to a running application;
:doc:`developer/architecture` shows how the pieces fit together;
:doc:`developer/data-model` and :doc:`developer/api-reference` are the two
references you will keep open.

**If you want to see it working**, the :doc:`demo-walkthrough` drives the five
flows the system exists for, end to end, on seeded demo data.

What it does
============

- **Accounts and roles.**  Email-and-password sign-in, seven roles held as
  Django groups, and self-service password reset.  See
  :doc:`developer/data-model` for the role table.
- **Membership.**  Two plans — Annual at $45 for 365 days and Life at $650 —
  bought online and activated the instant the payment clears.
- **Profiles.**  Contact details, DART affiliation, pilot certificate,
  medical, flight review, hours, and volunteer interests.
- **Aircraft.**  One shared register of airframes with insurance carriers
  , limits, and expiry dates, which members attach to their own profiles.
- **The leader check.**  One screen that answers "may this person fly this
  airplane for us today?" — membership, medical, and insurance in a single
  GO / NO-GO verdict.
- **Payments.**  Stripe (card, Apple Pay, Google Pay, Link) and PayPal, plus a
  mock provider for demonstrations and tests, with optional donations at
  checkout and month-by-month reporting.
- **Reminders.**  Scheduled renewal email at 60, 30, and 7 days before expiry,
  on the day, and 30 days after.
- **Reports.**  Membership and aircraft exports as CSV and PDF, payment
  exports as CSV, all with the same filters as the screen you exported them
  from.
- **Content.**  Wagtail page types, StreamField blocks, three themes, and a
  members-only wall that only current members and staff get past.
- **Operations.**  Health checks, database backups, restore, and reset, from
  the command line or the portal.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   demo-walkthrough
   user/index
   developer/index
