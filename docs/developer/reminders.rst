=================
Renewal reminders
=================

CalDART emails members before and after their membership runs out.  The whole
mechanism is one management command, one log table and ten templates; there is
no queue, no worker and no scheduler process.  A systemd timer runs the command
once a day, and everything else falls out of the data.

The code is in ``backend/apps/reminders/`` and the templates are in
``backend/templates/emails/``.


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
them: for kind *k*, the cohort is every membership whose ``ends_on`` falls in
the window ending at ``today - offset(k)``.


.. _reminders-window:

The catch-up window
===================

One scan covers three days of expiry dates for each kind, ``WINDOW_DAYS`` in
``apps/reminders/services.py``, counting back from that kind's own date.  A
member whose term ends 60 days from today is in the ``t60`` cohort today, and
is still in it on the next two runs.  A morning the timer never fired, or a run
that stopped early, is therefore made good the next day rather than stepping
over a cohort for good.

The window cannot send twice.  ``ReminderLog`` still allows one row per
``(user, membership, kind)``, so the overlap between consecutive runs is
skipped as ``already_sent``.  It cannot blur two kinds together either: three
days is shorter than the seven between ``t7`` and ``expired``, so no membership
is ever in two cohorts at once.

``expired`` is the exception, listed in ``EXACT_DAY_KINDS``.  "Your membership
expires today" is untrue the morning after, so a missed ``expired`` is dropped
rather than sent late; the member gets the ``post30`` note in due course.

Because a reminder can go out behind its nominal date, the day count in the
subject and body is computed from the dates themselves.  A ``t30`` reminder
sent two days late says "expires in 28 days", not 30.


What the scanner does
=====================

``apps.reminders.services.send_renewal_reminders`` is the single entry point.
The management command, ``POST /system/reminders/run`` and the systemd timer
all call it.  In order:

1. **Expire lapsed terms.**  Every ``Membership`` that is still ``active`` with
   an ``ends_on`` in the past is flipped to ``expired``.  This runs first so
   that the ``post30`` cohort is honestly labeled.
2. **Walk the five kinds in order.**  For each, select the memberships whose
   ``ends_on`` falls in that kind's window (:ref:`reminders-window`), excluding
   canceled ones.  Lifetime terms have no ``ends_on`` at all, so they never
   appear.
3. **Decide whether to send.**  A candidate is skipped, with a reason recorded
   in the summary, when:

   ``already_sent``
      a ``ReminderLog`` row already exists for this user, membership, and kind;
   ``inactive_user``
      the account has been deactivated;
   ``no_email``
      the account has no email address;
   ``lifetime``
      the member holds a lifetime term, whatever else is on file;
   ``auto_renew``
      the membership renews itself, so the automatic-renewal emails already tell
      the member what is happening to it.  That means an ``active`` mandate, or a
      ``pending`` one with a charge already scheduled; a ``paused`` or
      ``canceled`` mandate covers nothing and the reminders resume.  See
      :doc:`renewals`;
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
kind, how many were skipped broken down by reason, and how many failed broken
down by kind.


When a send fails
=================

The scan never stops at the first bad address.  Each send is attempted on its
own, and two outcomes are handled rather than raised:

**The mail server refuses the message** (an ``SMTPException``, or any other
``OSError`` from the connection).  The transaction rolls back, so no
``ReminderLog`` row survives and the reminder is still due.  A later run sends
it only while that member's ``ends_on`` is still inside the kind's window
(:ref:`reminders-window`), so the retry is the rest of the window and nothing
more.  For the four windowed kinds the window opens on the kind's own date and
runs for three days: a send that fails on its first or second day is tried
again the next morning, and one that fails on the third day — a send that was
already two days behind — is not, because the next run no longer has that term
in the cohort.  ``expired`` matches its own day alone, so a failed ``expired``
send is never retried: once that day is over the cohort is gone and the message
is not recovered — sending it late would tell the member their membership
expires today when it expired yesterday.  Their term already reads as expired
in the portal, and the next thing CalDART sends them is the ``post30`` note.
The failure is counted in ``failed`` and ``failed_by_kind``, and logged at ERROR
with the kind, the user id, the membership id and the exception class.
Addresses are deliberately left out of that line.

**Another run logged the same reminder first**, so the insert hits the unique
constraint.  That is not a failure: the other run is sending the email.  It is
logged at WARNING and counted as ``already_sent``.

Either way the scan carries on with the next member and returns its summary.
``manage.py send_renewal_reminders`` prints the failure count and exits
non-zero when it is not zero, which is what makes the systemd unit go to
``failed`` and show up in ``systemctl list-timers`` and the journal.  The
``POST /system/reminders/run`` payload carries ``{sent, skipped}`` alone, so a
failure reaches the operator through the log rather than through the response.


Running it
==========

Development::

  make reminders                          # today, for real
  make reminders DRY_RUN=1                # rehearse, write nothing
  make reminders TODAY=2027-01-01         # scan as of another date
  make reminders TODAY=2027-01-01 DRY_RUN=1

``DRY_RUN=0``, ``DRY_RUN=no``, ``DRY_RUN=false`` and an unset ``DRY_RUN`` all
send for real, and any other value stops ``make`` before the scan; the full
rule is in :ref:`make-switches`.

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
  failed           0
  would send 12, skipped 2

A dry run writes nothing at all: no email, no log row, and no membership status
flips.  It is safe on production.

The command exits 0 when ``failed`` is 0, and 1 with a ``CommandError`` on
stderr when it is not.  Everything it managed to send is still sent, and the
summary is still printed; the non-zero status is what the timer notices.

System administrators can also run the scan from ``/portal/system``, with the
same dry-run switch.  That endpoint is ``POST /system/reminders/run`` and
returns ``{"sent": n, "skipped": n}``.

In development, Mailpit catches everything: http://localhost:8025.


Scheduling
==========

Production runs it from a systemd timer, not cron, so that the run is a unit
with logs, status, and a catch-up policy:

``deploy/systemd/caldart-reminders.service``
   ``Type=oneshot``, runs ``manage.py send_renewal_reminders`` as the
   ``caldart`` user with ``EnvironmentFile=/etc/caldart/caldart.env``.

``deploy/systemd/caldart-reminders.timer``
   ``OnCalendar=*-*-* 07:00:00`` in the system timezone, ``Persistent=true`` so
   a machine that was off at 07:00 catches up when it comes back, and a five
   minute randomized delay so the scan does not collide with every other 07:00
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
it weekly.  The scanner is date-driven and idempotent, so running it more often
simply finds nothing new.  Keep the cadence daily, though: ``expired`` matches
its own day alone (:ref:`reminders-window`), so a timer that skips a day drops
that day's ``expired`` cohort for good.  Only the four windowed kinds tolerate a
slower timer, and only down to one run every three days, because the window is
three days wide; a weekly timer misses most of their cohorts as well.  With a
daily timer, ``Persistent=true`` and the overlap between runs cover a machine
that was off at 07:00.

**Changing which reminders exist** is a code change: add the kind to
``ReminderKind`` and ``REMINDER_OFFSETS``, add it to ``KIND_ORDER`` and a
subject to ``SUBJECTS`` in ``apps/reminders/services.py``, add the two
templates, and generate a migration for the new choice.  On the frontend, add
the kind to the ``ReminderKind`` union in ``frontend/src/portal/api/types.ts``,
then a label to ``KIND_LABELS`` and an entry to ``KIND_OPTIONS`` in
``frontend/src/portal/features/system/ReminderLog.tsx`` — ``KIND_LABELS``
names the kind in the log's table, and ``KIND_OPTIONS`` is what puts it in the
log's kind filter.


Templates
=========

Every kind renders two bodies from ``backend/templates/emails/``:

``reminder_<kind>.txt``
   The plain-text body, and the one most mail clients quote when replying.

``reminder_<kind>.html``
   The HTML alternative.  Extends ``reminder_base.html``, which holds the table
   layout, the inline styles and the footer, and exposes the blocks
   ``preheader``, ``heading``, ``lede``, ``body``, and ``cta_label``.

The HTML shell uses the ``duty`` palette (:doc:`theming`) with Georgia standing
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
``days``               days between ``today`` and ``expires_on``, unsigned
``today``              the date being scanned
``renew_url``          ``SITE_URL/portal/renew``
``site_url``           ``SITE_URL`` without a trailing slash
=====================  ====================================================

Subject lines are *not* in the templates; they are in ``SUBJECTS`` in
``services.py``, keyed by kind, with ``{org}`` and ``{days}`` substituted.

``org_name`` and ``contact_email`` come from ``org_name()`` and
``contact_email()`` in ``backend/caldart/mail.py``, so one organization name and
one contact address reach every email that reads them from there.  Both fall
back: the name to ``CalDART`` and the address to an empty string, which the
templates leave out rather than printing blank.  ``send_templated`` in that same
module renders and sends a ``.txt``/``.html`` pair the way this scanner does,
and attaches a document where one rides along; see :ref:`reports-receipts` for
the receipt PDF.

Every kind but ``expired`` states ``days`` in its subject and its body, so the
wording follows the dates when a reminder goes out behind its nominal day.

House voice: plain, specific, no exclamation marks, no emoji.  Say what expires
and when, give one link, and stop.


The log
=======

``ReminderLog`` records ``user``, ``membership``, ``kind``, ``sent_at``, and
``to_email``.  It exists to make the scanner idempotent, and it doubles as the
answer to "was this member ever told?".

Read it at ``GET /admin/reminders/log`` — open to ``account_admin`` as well as
``system_admin``, since it is a membership question as much as an operations
one — or on either of the two portal screens that show it.

.. _reminders-account-admin:

Both screens render the same table, the component
``frontend/src/portal/features/system/ReminderLog.tsx``: the twenty most recent
reminders, newest first, with a filter by kind.

``/portal/admin/reminders``
   **Reminders**, under *Administration*, guarded by ``account_admin``.  The
   log and nothing else, because starting a scan is a system administrator's
   job.  :doc:`/user/account-administrator-guide` describes it for the people
   who use it.

``/portal/system``
   The reminders panel of the System page, guarded by ``system_admin``.  The
   same table with the *Run now* button and the *Dry run* switch above it,
   which call ``POST /system/reminders/run``.

The endpoint is paginated and takes five parameters:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Parameter
     - Matches
   * - ``kind``
     - one of ``t60``, ``t30``, ``t7``, ``expired``, ``post30``
   * - ``from``, ``to``
     - dates, compared against ``sent_at`` in local time
   * - ``search``
     - the recipient address, or the member's email, first name or last name
   * - ``ordering``
     - ``sent_at`` or ``kind``, ``-`` prefixed for descending; the default is
       newest first

(``from`` is a Python keyword, so the filter is attached to the filterset after
the class is built rather than declared as an attribute — worth knowing if you
go looking for it and cannot find it.)

Deleting a log row makes that reminder eligible to be sent again.  That is the
supported way to re-send one to a member who never received it.


Testing
=======

``backend/tests/test_reminders.py`` covers the scanner: each kind on its own
offset and silence a day early, dedupe across runs, the expiry flip, the dry
run writing nothing, lifetime, and deactivated members being skipped, early
renewals being skipped, and the rendered content of every template.
``backend/tests/test_reminders_resilience.py`` covers the edges of the window
, one and two days late sending and three days late not, ``expired`` never going
out late, the day count in a late email, and the failure paths: a locmem
backend that refuses one address, the log line that names ids and no address,
a log row written under the scan to stand in for a racing run, and a failed
``expired`` send that the next day's run leaves alone.
``backend/tests/test_reminders_api.py`` covers the endpoints and their role
matrix.  Dates are pinned with ``freezegun`` where the code reads the clock,
and passed explicitly everywhere else.

Related
=======

:doc:`api-system` documents the reminder log and manual-run endpoints in
detail.
