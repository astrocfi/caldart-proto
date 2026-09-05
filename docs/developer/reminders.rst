=================
Renewal reminders
=================

CalDART emails members before and after their membership runs out.  The whole
mechanism is one management command, one log table and ten templates; there is
no queue, no worker and no scheduler process.  A systemd timer runs the command
once a day, and everything else falls out of the data.

Specified in PLAN §4.5 (what is sent) and §12 (when).


The five kinds
==============

Each kind is defined by an offset in days from the membership's ``ends_on``
date.  Negative offsets are before expiry.

``t60``
   60 days before expiry.  An early heads-up: renewing now keeps coverage
   unbroken, and it is a good moment to check medical and insurance dates.

``t30``
   30 days before expiry.  The main renewal nudge.

``t7``
   7 days before expiry.  Last call before the membership stops reading as
   current to DART leaders.

``expired``
   The expiry date itself.  The term still covers today; from tomorrow it does
   not.

``post30``
   30 days after expiry.  A win-back note, and the last message that membership
   ever produces.

The offsets live in one place, ``REMINDER_OFFSETS`` in
``backend/apps/reminders/models.py``, and the scanner derives its query from
them: for kind *k*, the cohort is every membership whose ``ends_on`` equals
``today - offset(k)``.


What the scanner does
=====================

``apps.reminders.services.send_renewal_reminders`` is the single entry point.
The management command, ``POST /system/reminders/run`` and the systemd timer
all call it.  In order:

1. **Expire lapsed terms.**  Every ``Membership`` that is still ``active`` with
   an ``ends_on`` in the past is flipped to ``expired``.  This runs first so
   that the ``post30`` cohort is honestly labelled.
2. **Walk the five kinds in order.**  For each, select memberships with the
   matching ``ends_on``, excluding cancelled ones.  Lifetime terms have no
   ``ends_on`` at all, so they never appear.
3. **Decide whether to send.**  A candidate is skipped, with a reason recorded
   in the summary, when:

   ``already_sent``
      a ``ReminderLog`` row already exists for this user, membership and kind;
   ``inactive_user``
      the account has been deactivated;
   ``no_email``
      the account has no email address;
   ``lifetime``
      the member holds a lifetime term, whatever else is on file;
   ``renewed``
      unbroken coverage now runs past this term.  For the pre-expiry kinds that
      means ``membership_status(user)["expires_on"]`` no longer equals this
      term's ``ends_on``; for ``post30`` it means the member is current again.

4. **Log, then send.**  The ``ReminderLog`` row is written first, inside the
   same transaction as the send.  A unique constraint on
   ``(user, membership, kind)`` means that if two runs race, the loser rolls
   back rather than sending a duplicate.

The function returns a ``ReminderRun``: the date scanned, whether it was a dry
run, how many terms were expired, how many emails were sent broken down by
kind, and how many were skipped broken down by reason.


Running it
==========

Development::

  make reminders                          # today, for real
  make reminders DRY_RUN=1                # rehearse, write nothing
  make reminders TODAY=2027-01-01         # scan as of another date
  make reminders TODAY=2027-01-01 DRY_RUN=1

Or directly::

  uv run backend/manage.py send_renewal_reminders --dry-run --today=2027-01-01

The command prints a structured summary::

  today            2027-01-01
  mode             dry run (nothing written)
  expired flipped  3
  sent             12
    t60            4
    t30            5
    t7             2
    expired        1
    post30         0
  skipped          2
    already_sent   1
    lifetime       1
  would send 12, skipped 2

A dry run writes nothing at all: no email, no log row, and no membership status
flips.  It is safe on production.

System administrators can also run the scan from ``/portal/system``, with the
same dry-run switch.  That endpoint is ``POST /system/reminders/run`` and
returns ``{"sent": n, "skipped": n}``.

In development, Mailpit catches everything: http://localhost:8025.


Scheduling
==========

Production runs it from a systemd timer, not cron, so that the run is a unit
with logs, status and a catch-up policy:

``deploy/systemd/caldart-reminders.service``
   ``Type=oneshot``, runs ``manage.py send_renewal_reminders`` as the
   ``caldart`` user with ``EnvironmentFile=/etc/caldart/caldart.env``.

``deploy/systemd/caldart-reminders.timer``
   ``OnCalendar=*-*-* 07:00:00`` in the system timezone, ``Persistent=true`` so
   a machine that was off at 07:00 catches up when it comes back, and a five
   minute randomised delay so the scan does not collide with every other 07:00
   job on the host.

Install and inspect::

  sudo cp deploy/systemd/caldart-reminders.service \
          deploy/systemd/caldart-reminders.timer /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now caldart-reminders.timer

  systemctl list-timers caldart-reminders.timer
  journalctl -u caldart-reminders -n 50

Running it by hand is safe at any time::

  sudo systemctl start caldart-reminders.service

**Changing the cadence.**  Edit ``OnCalendar`` in the timer and reload::

  sudo systemctl daemon-reload
  sudo systemctl restart caldart-reminders.timer

``OnCalendar=*-*-* 06:30:00`` moves it to 06:30; ``Mon *-*-* 07:00:00`` makes
it weekly.  Nothing else has to change — the scanner is date-driven and
idempotent, so running it more often simply finds nothing new, and running it
less often risks stepping over a cohort entirely, since a member is only in the
``t30`` cohort on exactly one day.  That is the reason for ``Persistent=true``.

**Changing which reminders exist** is a code change: add the kind to
``ReminderKind`` and ``REMINDER_OFFSETS``, add a subject to ``SUBJECTS`` in
``apps/reminders/services.py``, add the two templates, and generate a migration
for the new choice.


Templates
=========

Every kind renders two bodies from ``backend/templates/emails/``:

``reminder_<kind>.txt``
   The plain-text body, and the one most mail clients quote when replying.

``reminder_<kind>.html``
   The HTML alternative.  Extends ``reminder_base.html``, which holds the table
   layout, the inline styles and the footer, and exposes the blocks
   ``preheader``, ``heading``, ``lede``, ``body`` and ``cta_label``.

The HTML shell uses the ``sierra`` palette from PLAN §9 with Georgia standing
in for Fraunces, because webfonts do not load in most mail clients.  Both
bodies link to ``SITE_URL + /portal/renew``.

Context available in a template:

=====================  ====================================================
Variable               Meaning
=====================  ====================================================
``user``               the ``User`` the email is going to
``first_name``         their first name, falling back to the display name
``org_name``           ``SiteSettings.org_name``, or ``CalDART``
``contact_email``      ``SiteSettings.contact_email``, may be empty
``plan_name``          ``Annual`` or ``Life``
``expires_on``         the term's ``ends_on`` date
``days``               the kind's offset in days, unsigned
``today``              the date being scanned
``renew_url``          ``SITE_URL/portal/renew``
``site_url``           ``SITE_URL`` without a trailing slash
=====================  ====================================================

Subject lines are *not* in the templates; they are in ``SUBJECTS`` in
``services.py``, keyed by kind, with ``{org}`` substituted.

House voice: plain, specific, no exclamation marks, no emoji.  Say what expires
and when, give one link, and stop.


The log
=======

``ReminderLog`` records ``user``, ``membership``, ``kind``, ``sent_at`` and
``to_email``.  It exists to make the scanner idempotent, and it doubles as the
answer to "was this member ever told?".

Read it at ``GET /admin/reminders/log?kind=&from=&to=`` — open to
``account_admin`` as well as ``system_admin``, since it is a membership
question as much as an operations one — or in the reminders panel of
``/portal/system``, which shows the twenty most recent with a kind filter.

Deleting a log row makes that reminder eligible to be sent again.  That is the
supported way to re-send one to a member who never received it.


Testing
=======

``backend/tests/test_reminders.py`` covers the scanner: each kind on its exact
offset and silence a day either side, dedupe across runs, the expiry flip, the
dry run writing nothing, lifetime and deactivated members being skipped, early
renewals being skipped, and the rendered content of every template.
``backend/tests/test_reminders_api.py`` covers the endpoints and their role
matrix.  Dates are pinned with ``freezegun`` where the code reads the clock,
and passed explicitly everywhere else.
