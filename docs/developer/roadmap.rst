=======
Roadmap
=======

What this prototype deliberately leaves out, and what building it would
involve.  Nothing here is a defect: each item is either out of scope by
decision or an obvious next step from where the code stands.  The notes are
written for whoever picks the work up — where the seams
already are, and what would have to change.

Deliberate non-goals
====================

Four things are out of scope by decision rather than by omission:

**Backwards compatibility.**  There is no data to migrate and no external API
to keep stable.  Change a model and regenerate its migration rather than
stacking a fix-up; delete code a change makes dead.

**Data migration from the live site.**  The seeded content is example copy
paraphrased from caldart.org, not an import.  A real migration would need a
mapping from the existing member records onto :doc:`data-model`'s
``MemberProfile`` and ``Membership``, and a decision about how much history to
bring across.

**Internationalization.**  ``USE_I18N`` is on and ``LANGUAGE_CODE`` is
``en-us``, but no string is wrapped in ``gettext`` and no catalog exists.
See :ref:`roadmap-i18n`.

**Auto-renewing subscriptions.**  See below — it is the largest single item on
this page.

Payments and money
==================

Auto-renewing subscriptions
---------------------------

Today every term is bought outright: ``create_checkout`` makes a one-off
charge, ``mark_succeeded`` calls ``activate_term``, and the member is emailed
before expiry to do it again.  Recurring billing would mean:

- **Stripe Subscriptions or Billing** rather than a bare PaymentIntent, with a
  ``Price`` per ``MembershipPlan`` and a ``Customer`` per ``User``.  The
  ``Customer`` id is the missing column — there is nowhere to keep it.
- **PayPal Subscriptions** (a different API from Orders v2, which is what
  ``providers/paypal.py`` speaks).
- A **``Subscription`` model** — provider, provider reference, plan, status,
  current period end, cancel-at-period-end — with the webhook handlers to keep
  it in step.
- Rewriting the reminder scanner's audience: an auto-renewing member should be
  told their card is about to be charged, and told loudly when it fails, rather
  than being asked to renew.
- A cancellation and card-update surface in the portal, and the dunning policy
  that goes with a failed renewal.

The provider abstraction (``providers/base.py``: ``start``, ``confirm``,
``handle_webhook``) is the right seam to extend; the work is the state machine
around it, not the HTTP.

Receipts
--------

A member gets no document after paying.  Stripe is passed a ``receipt_email``,
so Stripe sends its own, but PayPal and the mock provider send nothing and
CalDART sends nothing itself.  A receipt would be a rendered PDF — the
``caldart.reports`` helpers already build PDFs — emailed on success and
downloadable from ``/portal/`` alongside the payment history.  A 501(c)(3) also
wants an annual contribution statement for tax purposes, which is the same
document over a year's payments.

Refunds
-------

``PaymentStatus`` includes ``refunded`` and nothing ever sets it.  Refunding
means refunding in the Stripe or PayPal dashboard and then correcting
CalDART by hand.  A refunds UI would need: an account-administrator action on
the payment row, a provider call (``stripe.Refund.create``, PayPal's refund
endpoint), the resulting status change, and a decision about the membership
term the payment bought — cancel it, shorten it, or leave it.  The webhook
handlers would need to accept refund events, which they ignore.

Members and accounts
====================

The Friend program
------------------

CalDART's real membership scheme has a *Friend of CalDART* tier: supporters who
are not pilots or ground crew, at a lower rate, without the operational
privileges.  The prototype ships two plans, Annual and Life, and no notion of a
tier that grants less.

The schema is most of the way there.  ``MembershipPlan`` is a table, so a
Friend plan is a row.  What is missing is the distinction in behavior:
membership currency is a single boolean question, and every current member gets
the same members-only content and appears the same way in a DART leader's
search.  A Friend tier needs a flag on the plan — call it ``grants_operational
_membership`` — and then a pass over every place that asks "is this person
current" to decide which question it is really asking.  Reporting and the
member list would want to filter by tier.

Multi-factor authentication
---------------------------

Sign-in is email and password, with rate limiting on login, registration, and
password reset.  Account, user, and system administrators can see and change
every member's details, and MFA on those roles is the obvious hardening step.

``django-otp`` with TOTP is the conventional route; it needs an enrollment
screen in the portal, a second step in the login flow, recovery codes, and a
policy decision about whether MFA is required for the administrative roles or
merely offered to everybody.  Wagtail's admin sign-in is a separate surface and
would need the same treatment.

Audit log
---------

Every privileged action writes one line to the ``caldart.audit`` logger: an
account edit by field name, a role change by slug, an activation, a member
creation or hard delete, a manual grant or term correction, an
administrator-triggered password reset, a backup created, downloaded, or
restored, a database reset, and each reminder run with its counts.  A refused
attempt is logged at WARNING with a reason.  :ref:`deploy-audit-log` lists the
actions and how to read them out of the journal.

The trail is a log, so it lives as long as the journal does, it holds ids
rather than values, and nobody can read it from the portal.  The next step is
an ``AuditEntry`` model — actor, action, target content type and id, a JSON
diff, timestamp — written alongside the log line, with a read-only screen for
system administrators, a retention policy and a filter by actor or target.
That is what turns "grep the journal" into "show me everything this
administrator did".  A fuller version also replaces the hard delete with a soft
one, so ``DELETE /admin/members/{id}`` stops taking the evidence with the row.

Communication
=============

SMS reminders
-------------

Renewal reminders are email only: five kinds, rendered from
``templates/emails/reminder_<kind>.{txt,html}`` and deduplicated by
``ReminderLog``.  During an actual activation, email is the wrong channel.

Adding SMS means a delivery provider (Twilio is the usual choice), a
``phone_verified`` flag and per-channel opt-in on ``MemberProfile`` —
``phone`` is already collected, but consent is not — short message templates
alongside the existing ones, and widening ``ReminderLog`` with a ``channel``
column so the ``(user, membership, kind)`` uniqueness becomes ``(user,
membership, kind, channel)``.  The scanner's structure does not otherwise
change: it already separates "who should be told" from "how they are told".

The larger prize behind it is broadcast messaging — telling a DART's members
about a callout — which is a different feature with the same plumbing.

.. _roadmap-i18n:

Internationalization
--------------------

Spanish is the obvious second language for a California volunteer
organization.  Doing it properly means all of: ``gettext`` on every server-side
string and template; a frontend message catalog and a runtime library;
Wagtail's ``wagtail.locales`` and translatable page trees for the CMS content,
which is the largest part; locale-aware dates and money; and a language
switcher that remembers its choice.  Nothing in the architecture prevents it,
but it touches every file that contains a sentence.

Operational
===========

**Restore from the portal.**  ``/portal/system`` can list, create, and download
backups but cannot restore one — deliberately, because wiping the database is
not a browser-tab action.  If it is ever added it needs a confirmation flow
worth the name, and probably a maintenance mode.

**Scheduled backups.**  ``deploy/systemd/`` ships a timer for the reminder
scan.  Backups are on demand — ``make backup``, the portal button, or the
service and timer that :doc:`backup-restore` spells out for an operator to
install by hand.  Shipping that pair in ``deploy/`` alongside the reminder one,
plus retention worth the name (keep N daily, M weekly) and off-host copies, is
a small piece of work with a large payoff.

**Observability.**  Logging goes to stdout for systemd to capture, and
``GET /system/health`` answers the basic questions.  There are no metrics, no
error tracking and no uptime check.

**Search.**  Wagtail's default database search backend is in use; a site of
this size does not need more, but a growing news archive eventually will.

Interface
=========

**Aircraft in the leader's verdict.**  The GO / NO-GO band is membership and
medical only; insurance is shown per airplane beside it, because which
airplane the member is about to fly is a fact the leader has and the system
does not.  Letting the leader pick the airplane and fold its insurance into a
single verdict would be a genuine improvement.

**Offline use.**  The leader check is the one screen used away from a desk, on
whatever signal a ramp has.  A service worker caching recent status cards
would make it dependable; nothing in the API prevents it.

**Bulk actions.**  Administrators can act on one member at a time.  Granting a
term to a selected set, or emailing a filtered list, would save real work in
the office.

Where to record the next thing
==============================

This page, and whichever page documents the behavior the change alters: the
documentation is the specification.  If the code and a page disagree, one of
them is wrong, and the pull request that finds the disagreement fixes it.
