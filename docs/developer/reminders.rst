=================
Renewal reminders
=================

CalDART emails members before and after their membership runs out.  The whole
mechanism is one management command, one log table and ten templates; there is
no queue, no worker and no scheduler process.  A systemd timer runs the command
once a day, and everything else falls out of the data.

The code is in ``backend/apps/reminders/`` and the templates are in
``backend/templates/emails/``.


The five stages
===============

Each kind is a *stage*: a span of expiry dates, not a single date.  One scan
sends a stage to every member whose ``ends_on`` falls in that stage's span that
day, and the reminder log makes sure each member gets each stage once.  For a
scan on day D:

``t60``
   Terms ending D+31 to D+60.  An early heads-up: renewing now keeps coverage
   unbroken, and it is a good moment to check medical and insurance dates.

``t30``
   Terms ending D+8 to D+30.  The main renewal nudge.

``t7``
   Terms ending D+1 to D+7.  Last call before the membership stops reading as
   current to DART leaders.

``expired``
   Terms that ran out on any of the seven days up to and including D.  On D
   itself the term still covers the day; after that it does not, and the email
   says how long ago it went.

``post30``
   Terms that ran out between D-60 and D-30.  A win-back note, and the last
   message that membership ever produces.

.. _reminders-stages:

Where the spans come from
=========================

The offsets live in one place, ``REMINDER_OFFSETS`` in
``backend/apps/reminders/models.py``, and one function turns them into spans:
``stage_span(kind, today)`` in ``apps/reminders/services.py``, which returns the
inclusive first and last expiry date of the stage.

A stage before expiry reaches back from its own date to the day after the date
of the stage nearer expiry, so the three of them tile the two months before a
term runs out with no gap and no overlap.  That is the point of stages: a
member who joins the register 23 days out is in ``t30`` that day, gets ``t7``
sixteen days later, and hears from CalDART twice, where three exact dates would
have reached them not at all.  A member who joins three days out gets ``t7``
and nothing earlier.

The two stages at expiry and after it reach back by their entry in
``POST_EXPIRY_REACH_DAYS``: ``expired`` by six days, because "your membership
has expired" stays worth saying for about a week, and ``post30`` by thirty, so
the win-back note covers a whole month of lapsed terms.  Nothing covers the
three weeks between those two spans, and nothing at all is sent about a term
that ran out more than sixty days ago.

Spans never overlap, so one scan sends one member at most one reminder.  Nor can
a stage repeat: ``ReminderLog`` allows one row per ``(user, membership, kind)``,
so the member is skipped as ``already_sent`` on every later day they are still
inside the span.  That same rule is what makes a missed morning harmless.  A day
the timer never fired, or a run that stopped early, is made good by the next
run, for every stage: only a gap longer than the span itself — a week for
``t7`` and ``expired`` — loses a member the stage they were in, and they then
get the next one.

Because a reminder goes out on any day of its span, the day count in the subject
and the body is computed from the dates themselves.  A ``t30`` email to a member
whose term ends in 28 days says 28 days, and a ``t7`` email on the last day says
"1 day left".

What the scanner does
=====================

``apps.reminders.services.send_renewal_reminders`` is the single entry point.
The management command, ``POST /system/reminders/run`` and the systemd timer
all call it.  In order:

1. **Expire lapsed terms.**  Every ``Membership`` that is still ``active`` with
   an ``ends_on`` in the past is flipped to ``expired``.  This runs first so
   that the ``post30`` stage is honestly labeled.
2. **Convert due friends.**  ``members.services.convert_due_friends`` stores
   every member whose ``friend_on`` is today or earlier as a friend, clears the
   date, and audits each as ``account.kind`` with ``to=friend`` and
   ``on=<friend_on>`` (:ref:`kinds of account <account-kinds>`).  A dry run converts nobody.
3. **Walk the five stages in order.**  For each, select the memberships whose
   ``ends_on`` falls in that stage's span (:ref:`reminders-stages`), excluding
   canceled ones, suspended ones (their holder deactivated their own account;
   see :ref:`api-deactivation`), and the terms of every account stored as a
   friend or carrying a ``friend_on`` date: a friend is never nagged to renew,
   and neither is a member who has asked to become one.  Such a term is not a candidate at all,
   so it appears in no skip count.  Lifetime terms have no ``ends_on`` at all,
   so they never appear.
4. **Decide whether to send.**  A candidate is skipped, with a reason recorded
   in the summary, when:

   ``already_sent``
      a ``ReminderLog`` row already exists for this user, membership, and kind;
   ``inactive_user``
      the account has been deactivated by an administrator, whose term is still
      ``active`` (an account its owner deactivated holds suspended terms, which
      are no candidates);
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

5. **Log, then send.**  The ``ReminderLog`` row is written and committed
   before the send is attempted.  A unique constraint on
   ``(user, membership, kind)`` means that if two runs race, the loser's
   insert fails immediately rather than sending a duplicate.

The function returns a ``ReminderRun``: the date scanned, whether it was a dry
run, how many terms were expired, how many emails were sent broken down by
stage, how many were skipped broken down by reason, and how many failed broken
down by stage.


When a send fails
=================

The scan never stops at the first bad address.  Each send is attempted on its
own, and two outcomes are handled rather than raised:

**The mail server refuses the message** (an ``SMTPException``, or any other
``OSError`` from the connection).  The ``ReminderLog`` row already written is
deleted by hand, so no row survives and the reminder is still due -- the
send itself still leaves a ``failed`` row in the email log
(:ref:`api-email-log`).  A later run sends
it while that member's ``ends_on`` is still inside the stage's span
(:ref:`reminders-stages`), so the retry is the rest of the span and nothing
more: a week for ``t7`` and ``expired``, three weeks or more for the others.
Once the term leaves the span the member is sent the stage they have reached
instead, and the refused message is not recovered.  A term that has left
``post30`` is past every stage, so nothing more is attempted.  The failure is
counted in ``failed`` and ``failed_by_kind``, and logged at ERROR with the
kind, the user id, the membership id and the exception class.  Addresses are
deliberately left out of that line.

**Another run logged the same reminder first**, so the insert hits the unique
constraint.  That is not a failure: the other run is sending the email.  It is
logged at WARNING and counted as ``already_sent``.

Either way the scan carries on with the next member and returns its summary.
``manage.py send_renewal_reminders`` prints the failure count and exits
non-zero when it is not zero, which is what makes the systemd unit go to
``failed`` and show up in ``systemctl list-timers`` and the journal.  The
``POST /system/reminders/run`` payload carries
``{sent, skipped, failed, skipped_by_reason, actions}``, so the System screen
says why a thin run was thin without anybody reading the log.


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
  would email t60 to Maria Alvarez <maria@example.org> on 2027-03-02
  would email t30 to Sam Ochoa <sam@example.org> on 2027-01-31
  would send 12, skipped 2

The lines after the counts are the run's ``actions``: one per reminder, naming
the member, their address and the day their term runs out.  A live run prints
``emailed t60 to ...`` instead.  They are what turns "twelve reminders" into
"these twelve people", which is the thing worth checking before a live run.

A dry run writes nothing at all: no email, no log row, and no membership status
flips.  It is safe on production.

The command exits 0 when ``failed`` is 0, and 1 with a ``CommandError`` on
stderr when it is not.  Everything it managed to send is still sent, and the
summary is still printed; the non-zero status is what the timer notices.

System administrators can also run the scan from ``/portal/system``, with the
same dry-run switch.  That endpoint is ``POST /system/reminders/run`` and
returns ``{"sent": n, "skipped": n, "failed": n, "skipped_by_reason": {...},
"actions": [...]}``, the same actions the command prints; see :doc:`api-system`.

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
simply finds nothing new, and a missed morning costs nothing: the stages are
spans, so the next run finds everyone the missed one would have
(:ref:`reminders-stages`).  A weekly timer is the point at which that stops
being true, because ``t7`` and ``expired`` are seven days wide: a member can
pass through one of them between two runs.  Keep the cadence daily, and let
``Persistent=true`` cover a machine that was off at 07:00.

**Changing which reminders exist** is a code change: add the stage to
``ReminderKind`` and ``REMINDER_OFFSETS``, add it to ``KIND_ORDER`` and a
subject to ``SUBJECTS`` in ``apps/reminders/services.py``, give it an entry in
``POST_EXPIRY_REACH_DAYS`` if it sits at or after expiry, add the two
templates, and edit the migration for the new choice.  Adding a stage before
expiry narrows the span of the stage nearer expiry, since the spans tile.  On
the frontend, add the kind to the ``ReminderKind`` union in
``frontend/src/portal/api/types.ts``,
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
``days_ago``           days since ``expires_on``, negative while the term runs
``today``              the date being scanned
``renew_url``          ``SITE_URL/portal/renew``
``site_url``           ``SITE_URL`` without a trailing slash
=====================  ====================================================

Subject lines are *not* in the templates; they are in ``SUBJECTS`` in
``services.py``, keyed by kind, with ``{org}``, ``{days}`` and ``{plural}``
substituted -- ``{plural}`` is the "s" a count of one drops.  ``expired`` has a
second subject beside its entry, ``EXPIRED_SUBJECT_DAYS_AGO``, used when the
term ran out before the day of the scan.

``org_name`` and ``contact_email`` come from ``org_name()`` and
``contact_email()`` in ``backend/caldart/mail.py``, so one organization name and
one contact address reach every email that reads them from there.  Both fall
back: the name to ``CalDART`` and the address to an empty string, which the
templates leave out rather than printing blank.  ``send_templated`` in that same
module renders and sends a ``.txt``/``.html`` pair the way this scanner does,
and attaches a document where one rides along; see :ref:`reports-receipts` for
the receipt PDF.

Every stage states its real distance from the expiry date, so the wording
follows the dates wherever in the span a member is reached.  ``expired`` reads
"today is the last day" on the expiry day and "your membership has expired ...
N days ago" after it, switching on ``days_ago``.

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

Every reminder is also recorded in the email log, under the purpose
``reminder_<kind>``, along with every other email the system sends
(:ref:`api-email-log`).  The two logs answer different questions: the reminder
log is the key that keeps a stage from repeating, and the email log is the record
of the message, with its subject and whether the mail server took it.  A refused
reminder leaves no ``ReminderLog`` row, so it stays due, but the send is still
recorded as a ``failed`` row in the email log, the same as any other refused
email.

.. _reminders-account-admin:

Both screens render the same table, the component
``frontend/src/portal/features/system/ReminderLog.tsx``: the twenty most recent
reminders, newest first, with a filter by kind.

``/portal/admin/reminders``
   **Reminders**, under *Administration*, guarded by ``account_admin``.  The
   log and nothing else, because starting a scan is a system administrator's
   job.  :doc:`/user/admin/reminders` describes it for the people
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

``backend/tests/test_reminder_stages.py`` covers the spans: a table over every
expiry date from seventy days before a scan to seventy days after it, naming the
one stage that covers each, the scan sending that stage, the days between the
spans sending nothing, and the ``expired`` wording on the expiry day and after
it.  ``backend/tests/test_reminders.py`` covers the scanner: each stage on its
own date, silence outside the stages, dedupe across runs, the expiry flip, the
dry run writing nothing, lifetime, and deactivated members being skipped, early
renewals being skipped, and the rendered content of every template.
``backend/tests/test_reminders_resilience.py`` covers late runs -- one and two
days late still sending, a run late enough to miss a stage sending the next one,
nothing at all after ``post30`` -- the day count in a late email, and the
failure paths: a locmem backend that refuses one address, the log line that
names ids and no address, a failed send still leaving a ``failed`` row in the
email log, a log row written under the scan to stand in for a racing run, and a
retry that the rest of the span allows.
``backend/tests/test_reminders_api.py`` covers the endpoints and their role
matrix.  Dates are pinned with ``freezegun`` where the code reads the clock,
and passed explicitly everywhere else.

Related
=======

:doc:`api-system` documents the reminder log and manual-run endpoints in
detail.
