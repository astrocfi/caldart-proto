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

**Bulk email beyond email.**  :doc:`bulk-email` sends one email to many people,
and nothing else.  Five things were considered and set aside: a second person
approving an email before it goes, SMS, tracking who opens an email or clicks its
links, an archive of past emails open to everybody, and members reading their own
transactional mail (receipts, reminders, password links) on **Messages**.

Members and accounts
====================

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
restored, a database reset, each reminder run with its counts, and every step of a
bulk email: queued, canceled, stopped, sent the rest, retried, refused by the
sender, and sent, with the templates, recipient groups, email types, opt-outs, and
callout answers around it.  A refused attempt is logged at WARNING with a reason.  :ref:`deploy-audit-log` lists the
actions and how to read them out of the journal.

The trail is a log, so it lives as long as the journal does, it holds ids
rather than values, and nobody can read it from the portal.  The next step is
an ``AuditEntry`` model — actor, action, target content type and id, a JSON
diff, timestamp — written alongside the log line, with a read-only screen for
system administrators, a retention policy and a filter by actor or target.
That is what turns "grep the journal" into "show me everything this
administrator did".

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

Broadcast messaging, telling a DART's members about a callout, is built by email:
:doc:`bulk-email` sends mission callouts and collects the answers.  SMS for bulk
email was set aside (`Deliberate non-goals`_); SMS for renewal reminders is still
open.

Bulk email
----------

:doc:`bulk-email` is complete for CalDART management, DART leaders, and the people
they write to.  Four next steps are known:

* The **Mail delivery** check reads the DMARC record at the From address's domain
  only.  A receiving server falls back to the organizational domain's record when a
  subdomain has none, so a site sending from a subdomain is reported as failing
  when it is not; the check should follow the same fallback, with the public suffix
  list to find the organizational domain.
* A mission callout's reminders are further rounds of copies of the same email.
  The Sent page's counts include them, but its table and its download list only the
  first round, so a failed reminder has no line of its own.
* The rich text editor shows an inserted field as its raw token, such as
  ``{first_name}``; showing it as a named chip would keep a sender from breaking it.
* A DART leader's email goes to the DART on their own profile, which they choose on
  **My profile**, and a member's own change of DART writes no audit line.

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

**Restore from the portal.**  ``/portal/system/health`` can list, create, and download
backups but cannot restore one — deliberately, because wiping the database is
not a browser-tab action.  If it is ever added it needs a confirmation flow
worth the name, and probably a maintenance mode.

**Off-host backups.**  ``caldart-backup.timer`` takes a dump every night and
prunes those older than ``BACKUP_RETENTION_DAYS`` (:doc:`backup-restore`).  Every
copy stays on the server itself, and the retention is one number of days.  Copying
each dump off the host, and keeping weeklies longer than dailies, is a small piece
of work with a large payoff.

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

**Bulk actions.**  Administrators act on one member at a time, apart from email,
which :doc:`bulk-email` sends to a filtered list.  Granting a term to a selected set
would save real work in the office.

Where to record the next thing
==============================

This page, and whichever page documents the behavior the change alters: the
documentation is the specification.  If the code and a page disagree, one of
them is wrong, and the pull request that finds the disagreement fixes it.
