========
Overview
========

CalDART's website has two halves. The **public site** is the home page, the
directory of DARTs (Disaster Airlift Response Teams, local groups of volunteer
pilots and ground crew at one airport), the news, the events, and the contact and
donation pages. Anybody can read it. The **member portal** is where you sign in,
and what it shows you depends on the roles your account holds: members keep their
own details current, DART leaders check whether somebody is fit to fly, and
administrators look after accounts, money, the website, and the system.

This page is the shape of the whole thing: the three kinds of people the site knows,
what a membership is and how it runs its course, and the roles. :doc:`quick-start`
walks through the first things you will do, and :doc:`member/index` describes every
screen you will use.


Members, friends, and donors
============================

Every account belongs to one of three kinds of person.

**Member**
  Pays dues each year, or once for a Life plan. A member's membership is current,
  expiring soon, or expired, and CalDART sends renewal reminders as the end of a
  term comes near. A member can add a contribution to any payment.

**Friend**
  A friend of CalDART has the same portal as a member (the profile, the aircraft,
  the payments, and the dashboard) but pays no dues. Nothing expires, no renewal
  reminder is ever sent, and members-only pages stay closed. A friend can give
  whenever they like, and becomes a member by paying for a plan. A member can
  become a friend, and a friend a member, from the portal.

**Donor**
  Somebody who gave to CalDART from the public donation page without joining.
  CalDART keeps the gifts and the receipts, but a donor has no password, cannot
  sign in, and appears in no member list. A donor who later joins, with the same
  email address, keeps every gift.

Members and friends sign in to the same portal. A donor does not.


What membership means
=====================

A membership is made of **terms**. A term is one plan bought, or granted by an
administrator, with a start date and an end date. You are current whenever a term
covers today, up to and including its last day. An Annual term runs 365 days. A Life
term has no end date and never runs out.

Buying a plan a second time does not replace the first term; it adds another after
it. So renewing early never loses you days: the new term starts the day after your
present one ends. Renewing after you lapse starts the new term today.

A current membership opens the members-only pages of the public site, and it is the
first thing a DART leader checks before letting you fly a mission.

.. only:: graphviz

   .. graphviz::
      :caption: The life of a membership. A solid box is a state CalDART works out
                for you. A dashed box is a warning or a special case inside one:
                *Expiring soon* is still current, and *Life member* is a current
                term with no end date. The boxes at the foot are the five renewal
                emails, in the order they are sent.
      :alt: The states of a CalDART membership, from visitor to expired, drawn top to bottom

      digraph member_lifecycle {
          rankdir=TB;
          bgcolor="transparent";
          nodesep=0.35;
          ranksep=0.45;
          node [shape=box, style="rounded", fontname="Helvetica", fontsize=12];
          edge [fontname="Helvetica", fontsize=11];

          Visitor [label="Visitor\nno account yet", style="rounded,dashed"];
          NoMembership [label="No membership\naccount and profile,\nno term has started"];
          Friend [label="Friend\nno dues, no expiry"];
          Current [label="Current\na term covers today"];
          Life [label="Life member\nnever expires", style="rounded,dashed"];
          Expiring [label="Expiring soon\n30 days or fewer left", style="rounded,dashed"];
          Expired [label="Expired\nthe last term ran out"];

          Visitor -> NoMembership [label=" join as a member"];
          Visitor -> Friend [label=" join as a friend"];
          NoMembership -> Current [label=" payment clears, or\n an administrator\n grants a term"];
          Friend -> Current [label=" pays for a plan"];
          Current -> Life [label=" buys the Life plan"];
          Current -> Expiring [label=" 30 days left", style=dashed];
          Expiring -> Expired [label=" end date passes"];
          Expiring -> Current [label=" renews early"];
          Expired -> Current [label=" renews"];
          Current -> Friend [label=" becomes a friend,\n from the day after\n the term ends", style=dashed, constraint=false];
          Expired -> Friend [label=" becomes a friend", constraint=false];

          subgraph cluster_reminders {
              label="Renewal emails, one per term and stage";
              fontname="Helvetica";
              fontsize=11;
              style=dashed;
              color="gray";
              node [fontsize=11];
              T60 [label="31 to 60 days before"];
              T30 [label="8 to 30 days before"];
              T7 [label="1 to 7 days before"];
              TEnd [label="the day it ends,\nor up to 6 days after"];
              TPost [label="30 to 60 days after"];
              T60 -> T30 -> T7 -> TEnd -> TPost;
          }

          Expired -> T60 [style=invis];
      }

.. only:: not graphviz

   Install Graphviz and rebuild for a drawn version of this diagram. The drawing and
   the text below describe the same states and the same moves between them.

   .. code-block:: text

      Visitor (no account yet)
        |                         \
        | join as a member         \ join as a friend
        v                           v
      No membership               Friend (no dues, no expiry)
        |                           |
        | payment clears, or an     | pays for a plan
        | administrator grants one  |
        v                           v
      Current (a term covers today) <=====================.
        |            \                                     |
        | 30 days     \ buys the Life plan                 |
        | left         v                                   |
        |            Life member (never expires)           |
        v                                                  |
      Expiring soon (still current) ==== renews early ====>|
        |                                                  |
        | end date passes                                  |
        v                                                  |
      Expired (the last term ran out) ===== renews =======>'

      A member who becomes a friend while current stays current until the term
      ends and is a friend from the next day. An expired member who becomes a
      friend is one at once.

      Renewal emails, one per term and stage, each linking to the renewal page:

        31 to 60 days before
        8 to 30 days before
        1 to 7 days before
        the day it ends, or up to 6 days after
        30 to 60 days after

What each state means:

**No membership**
  You have an account and can sign in, but no term has started. The portal works;
  members-only pages do not. You land here if you stop the join wizard before
  paying.

**Current**
  A term covers today. Members-only pages open, and the membership half of a DART
  leader's check passes.

**Expiring soon**
  Still current, with 30 days or fewer to run. The dashboard warns you and puts the
  **Renew** button first. Nothing is taken away.

**Expired**
  Your last term ran out, and no other covers today. The day after the end date is
  the first day it no longer counts. You can still sign in, see your profile, and
  renew; members-only pages show a wall.

**Life member**
  A Life term never runs out, so you are never asked to renew or sent a reminder.

**Friend**
  No dues, so nothing expires and nothing reminds you. Terms you held as a member
  stay in your history but no longer count.


What CalDART does about expiry
==============================

Each night CalDART marks terms whose end date has passed as expired, makes a friend
of every member whose day to become one has come, and sends the renewal reminders.
There are five, each covering a stretch of the calendar, so you receive every one
whichever day you joined. Each is sent once per term, and renewing stops the rest.
Life members, friends, deactivated accounts, and members whose automatic renewal
covers the term are not sent them. :doc:`member/renew` lists the subject lines.


The roles
=========

Every account holds one or more roles, and the portal's menu shows only the screens
your roles open. :doc:`roles` lists every screen each one reaches.

**Member**
  Every member and friend holds it. It opens your own dashboard, profile, aircraft,
  payments, donations, and renewal.

**DART leader**
  Checks, before a mission, whether a member is current to fly: membership, medical,
  pilot certificate, and aircraft insurance. Reads the member list and downloads it.

**User administrator**
  Looks after accounts: who holds which role, activating and deactivating, and
  password reset links.

**Treasurer**
  Looks after the money: every payment, refunds, automatic renewals, reconciliation
  against the bank, donors, and the financial reports.

**Account administrator**
  Looks after the membership records: members, their terms, the aircraft register,
  the DARTs, the reminder log, and the reports and rosters sent by email. Can check
  members as a DART leader does.

**Website administrator**
  Writes and publishes the public site's pages, news, and events.

**System administrator**
  Can do everything above, and looks after the system itself: health, backups, and
  the jobs that run each night.
