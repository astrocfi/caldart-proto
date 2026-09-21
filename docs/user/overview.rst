========
Overview
========

CalDART is one website with two halves.  The **public site** — the home page,
the Disaster Airlift Response Team (DART) directory, the news and the contact
page — is open to anybody with the address.  The **member portal** at
``/portal/`` is where you sign in, and what it shows you depends on the roles
your account holds: members keep their own details current, DART leaders check
whether somebody is fit to fly, and administrators look after accounts, money,
content and the server.

Almost everything else in this guide is a chapter about one of those jobs.
This page is the shape of the whole thing: how a membership begins, how it
ends, and what the site does about it in between.  Read
:doc:`getting-started` next for signing in and finding your way around.


The membership lifecycle
========================

A membership is made of **terms**.  A term is one plan bought (or granted by an
administrator) with a start date and an end date, and your membership is
current whenever a term covers today.  Buying the Annual plan a second time
does not replace the first term; it adds another one after it.

.. only:: graphviz

   .. graphviz::
      :caption: The life of a membership.  A **solid box** is one of the three
                states the site computes for you: ``none``, ``current`` and
                ``expired``.  A **dashed box** is not a state of its own —
                *Expiring soon* is the portal's warning inside *Current*, and
                *Life member* is a current term with no end date.  The boxes at
                the bottom are the five renewal emails, in the order they are
                sent; every one of them links straight to the renewal page.
      :alt: State diagram of a CalDART membership from visitor to expired

      digraph member_lifecycle {
          rankdir=LR;
          bgcolor="transparent";
          node [shape=box, style="rounded", fontname="Helvetica", fontsize=10];
          edge [fontname="Helvetica", fontsize=9];

          Visitor [label="Visitor\l  no account yet\l", style="rounded,dashed"];
          NoMembership [label="No membership\l  account and profile,\l  no term has started\l"];
          Current [label="Current\l  a term covers today\l  members-only content opens\l"];
          Expiring [label="Expiring soon\l  current, 30 days or fewer left\l", style="rounded,dashed"];
          Expired [label="Expired\l  the last term has run out\l  members-only content closes\l"];
          Life [label="Life member\l  a term with no end date\l  never expires, never reminded\l", style="rounded,dashed"];

          Visitor -> NoMembership [label="join wizard:\lname, email, password,\lthen the profile"];
          NoMembership -> Current [label="the payment clears, or an\ladministrator grants a term"];
          Current -> Expiring [label="30 days left", style=dashed];
          Expiring -> Expired [label="the end date passes"];
          Expiring -> Current [label="renew early: the term starts\lthe day after this one ends"];
          Expired -> Current [label="renew: the term starts today"];
          Current -> Life [label="buy the Life plan"];
          NoMembership -> Life [label="buy the Life plan"];

          subgraph cluster_reminders {
              label="Renewal email, sent once per term and kind";
              fontname="Helvetica";
              fontsize=9;
              style=dashed;
              color="gray";
              node [shape=box, style="rounded", fontsize=9];
              edge [color="gray50"];

              T60 [label="60 days before"];
              T30 [label="30 days before"];
              T7 [label="7 days before"];
              TEnd [label="the day it ends"];
              TPost [label="30 days after"];

              T60 -> T30 -> T7 -> TEnd -> TPost;
          }

          TEnd -> Expired [style=dotted, label="the same day"];
      }

.. only:: not graphviz

   Install Graphviz and rebuild for a drawn version of this diagram.  The
   drawing and the text below describe the same states and the same moves
   between them.

   .. code-block:: text

      Visitor  ---- join wizard: name, email, password, then the profile ---.
      (no account yet)                                                      |
                                                                            v
                                                              .---------------------.
        .------- buy the Life plan ---------------------------|   No membership     |
        |                                                     |   account and       |
        |                                                     |   profile, no term  |
        |                                                     |   has started       |
        |                                                     '---------------------'
        |                                                                |
        |                                    the payment clears, or an   |
        |                                    administrator grants a term |
        v                                                                v
      .------------------------.                             .---------------------.
      |  Life member           |<---- buy the Life plan ------|   Current           |
      |  a term with no end    |                             |   a term covers     |
      |  date; never expires,  |                             |   today; members-   |
      |  never reminded        |                             |   only content opens|
      '------------------------'                             '---------------------'
                                                                   |         ^
                                                    30 days left   |         |
                                                                   v         |
                                                      .-------------------.  |
                                                      | Expiring soon     |--'
                                                      | current, 30 days  |  renew early:
                                                      | or fewer left     |  the term starts
                                                      '-------------------'  the day after
                                                                   |         this one ends
                                              the end date passes  |
                                                                   v
                                                      .-------------------.
                                                      | Expired           |
                                                      | the last term has |---.
                                                      | run out; members- |   |
                                                      | only content      |   | renew: the
                                                      | closes            |<--' term starts
                                                      '-------------------'    today

      Renewal email, sent once per term and kind, each linking to the
      renewal page:

        60 days before  ->  30 days before  ->  7 days before  ->
        the day it ends (the same day the term becomes Expired)  ->
        30 days after

      "Expiring soon" and "Life member" are drawn dashed above because neither
      is a state of its own: the first is the portal's warning inside Current,
      and the second is a current term with no end date.


What each state means
---------------------

**No membership**
  You have an account and can sign in, but no term has ever started.  The
  portal works; members-only pages do not.  This is where you land if you stop
  the join wizard before paying.

**Current**
  A term covers today.  Members-only pages open, your dashboard shows a
  **Current** chip and the date your membership runs to, and the membership
  half of a DART leader's check passes.

**Expiring soon**
  Still current, with 30 days or fewer to run.  The portal turns the dashboard
  chip to **Expiring soon** and gives the **Renew** button the lead.  Nothing
  is taken away.

**Expired**
  A term started and ran out, and no other term covers today.  You can still
  sign in, see your own profile and renew; members-only pages show the wall
  instead of the page.

**Life member**
  A Life term has no end date, so it never runs out.  You are never asked to
  renew and never sent a reminder.

Renewing never loses you days.  If you renew while you are current, the new
term starts **the day after** your present one ends, and your dashboard shows
the later date straight away.  If you renew after lapsing, the new term starts
today.  :doc:`member-guide` walks through the screen itself.


What the site does about expiry
-------------------------------

A nightly scan does two things: it marks terms whose end date has passed as
expired, and it sends the renewal emails.  You get one 60 days before your term
ends, one at 30 days, one at 7 days, one on the day it ends, and one 30 days
after it has lapsed.

Each email is sent once per term, so a scan that runs twice in a day does not
mail you twice, and renewing stops the rest of the series.  Life members, and
accounts that have been deactivated, are never mailed.  Every email links to
the renewal page.


Where to go next
================

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - You want to
     - Read
   * - Sign in, or get back in without your password
     - :doc:`getting-started`
   * - Join, renew, or keep your profile current
     - :doc:`member-guide`
   * - Understand what you were charged and find a receipt
     - :doc:`payments`
   * - Add an airplane and keep its insurance current
     - :doc:`aircraft`
   * - Check whether a member may fly for us today
     - :doc:`dart-leader-guide`
   * - Look after accounts, roles and membership terms
     - :doc:`user-administrator`, :doc:`account-administrator-guide`
   * - Edit the public site
     - :doc:`website-administrator-guide`
   * - Back up, restore or check the health of the system
     - :doc:`system-administrator-guide`
