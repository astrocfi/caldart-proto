=================
Scheduled reports
=================

CalDART emails reports on its own: a **subscription** sends one report to one
address on a schedule, and each DART is sent its **roster** once a month.  As
with the renewal reminders (:doc:`reminders`), there is no queue and no worker:
one management command, run daily by a systemd timer, sends whatever is due,
and everything else falls out of two dates on the rows.

Every file attached is built by ``caldart.reports.build_report`` exactly as the
report's download builds it (:doc:`reports`), and every email goes through
``caldart.mail.send_templated``, so the email log records each one
(:ref:`api-email-log`).  The code is in ``backend/apps/reports/``, the templates
are ``scheduled_report`` and ``dart_roster`` in ``backend/templates/emails/``,
and the endpoints are in :doc:`api-reports`.


Subscriptions
=============

A ``ReportSubscription`` (:ref:`data-model-reports`) names the report by its
slug, the params it is built with (``filters``, ``period`` included, and
``columns``), which files to attach (``csv``, ``pdf`` or ``both``), the
schedule (``cadence`` and, for ``weekly``, ``weekday``), and where it goes.
The finance roles set them up, each for the reports they may read.

The schedule
------------

``next_due_after(cadence, weekday, day)`` in ``apps/reports/schedule.py`` gives
the first date strictly after ``day`` on which the cadence falls:

``weekly``
   the next ``weekday`` (0 Monday to 6 Sunday) after ``day``, a week later when
   ``day`` is that weekday;
``monthly``
   the first of the next month;
``quarterly``
   the next January 1, April 1, July 1 or October 1;
``yearly``
   the next January 1.

A subscription's ``next_due_on`` starts as ``next_due_after(..., today)``.  The
daily run sends every active subscription whose ``next_due_on`` is today or
earlier and, after a successful send, moves it to ``next_due_after(...,
today)``: a subscription due on a day the timer missed is sent by the next run,
once, and then falls back into step.  A failed send leaves it where it was, so
tomorrow's run retries it.  Changing the cadence or the weekday moves it to the
schedule's next day after the edit; **Send now** leaves it.

A ``period`` among the filters (``this_month``, ``last_month``, ``this_year``,
``last_year``) is resolved on the day the report is built, so a monthly
subscription that says ``last_month`` always carries the month before the one it
is sent in.

The demo seed sets every subscription's ``next_due_on`` to the day it runs, so
the daily job always has three ready to send: the membership report monthly to
the account administrator, this year's payments quarterly to the treasurer, and
the aircraft register weekly, also to the account administrator, and every
DART roster, whose ``roster_sent_at`` the seed leaves unset, is due as well.

Who may receive a report
------------------------

The recipient is named by address when the subscription is set up:

* When an account holds the address (compared without regard to case), the
  subscription is bound to that account, and it is refused unless the account
  holds a role that may read the report — the same rule the report's download
  applies.  A treasurer cannot be subscribed to the membership report, for
  example, whose medical and certificate data is not theirs to read.
* When no account holds it, the person setting it up must tick a box
  confirming that the address, outside CalDART, may receive the report.  The
  subscription is then bound to the bare address.

The rule is checked again at every send, against the recipient as it is that
day.  A subscription bound to an account is sent to the account's current
address, and its ``recipient_email`` follows it.  A bare address that an
account has since taken is bound to that account, so its roles decide from then
on.  An account that has lost the role, or been deactivated, or that took a
bare address without a role that may read the report, is skipped as
``not_permitted`` and the subscription is paused; resuming it is refused until
the account may read the report again.

The email
---------

The subject is ``CalDART report: <title> (<Month D, YYYY>)``.  The body names
the report, the filters the report applied (a ``period`` reads as the dates it
resolved to, as the PDF's subtitle prints it), the schedule, who set it up, and the attached files,
and says that an account administrator or a treasurer can change or stop it.
The email log records it under the purpose ``scheduled_report``, with the
recipient's account and its display name as the row's name when there is one,
and no name for a bare address.


DART rosters
============

Each active DART is sent its roster once a month, one email to each person on
the DART's list (``DartContact``) who is ticked to receive it
(``receives_roster``).  The roster is the membership report for the DART —
``{"dart": <id>, "ordering": "name"}`` — with the columns in
``ROSTER_COLUMNS``: name, phone, email, certificate, medical, medical expiry,
aircraft and membership expiry, as a PDF built once per DART.

A DART is due on any run in a month in which it has not yet been sent one:
``roster_sent_at`` is null, or falls before the first of the run's month.  So
the roster goes out on the first of the month, or on the first run after it if
the timer missed the day.  ``roster_sent_at`` is stamped when every email went
out; a refused one leaves the DART due, and the next run sends the roster to all
its people again, since a repeated roster does less harm than a missing one.

A DART with nobody ticked who has an address is skipped as ``no_recipients``.
Otherwise each ticked person without an address is skipped as ``no_email`` and
everyone else is sent the roster.  The subject is
``<DART name> roster (<Month D, YYYY>)``, and the body says how many members it
lists and that the DART's leaders may ask a CalDART account administrator to
change who receives it.  The email log records it under the purpose
``dart_roster``, naming the contact as the row's own name -- a DART contact
holds no account, so this is the only way its recipient's name reaches the
log.

``POST /reports/rosters/send`` sends every active DART's roster at once,
whatever the date, for the account administrator's **Send rosters now** button.


The run
=======

``apps.reports.services.run_scheduled_reports`` is the single entry point: the
management command, ``POST /system/reports/run`` and the timer all call it.
It sends every subscription that is due, then every roster that is due, and
returns a ``ReportRun``:

``sent``
   the emails that went out, or in a dry run would have;
``skipped`` and ``skipped_by_reason``
   ``not_permitted``, ``no_recipients`` and ``no_email``, with one entry per
   reason that occurred;
``failed``
   the emails the mail server refused (an ``SMTPException`` or another
   ``OSError``), and the reports the stored filters could no longer build.
   Each is logged at ERROR with the subscription or DART id and the exception
   class, never the address;
``actions``
   one line per email: kind ``report`` with the recipient and, in ``detail``,
   the report's title and formats, or kind ``roster`` with the person and the
   DART.

One recipient's problem never stops the run.  A dry run writes nothing — no
email, no pause, no stamp, and no date moves on — and lists exactly the emails
a live run would send: it builds each subscription's report, so one whose
stored filters no longer build is counted in ``failed`` there too.

Each subscription and each DART is sent inside its own transaction that holds
its row (``select_for_update(skip_locked=True)``) and checks again that it is
still due.  When two runs overlap — the timer and ``POST /system/reports/run``,
say — the one that takes a row sends it and the other passes it by, so nobody
is sent the same report twice.  **Send now** takes no such turn: it sends
whatever the date, by design.

The run ends with one ``reports.run`` audit line carrying ``dry_run``,
``sent``, ``skipped`` and ``failed``; a **Send now** writes one ``report.send``
line naming the subscription or, per DART, the roster (see
:ref:`deploy-audit-log`).

The command
-----------

.. code-block:: console

   $ cd backend
   $ uv run python manage.py send_scheduled_reports --dry-run --today 2026-11-01
   today            2026-11-01
   mode             dry run (nothing sent)
   sent             34
   skipped          0
   failed           0
   would email report to Curtis Whitfield <accountadmin@example.org> (CalDART membership report, PDF)
   ...
   would send 34, skipped 0

``--today`` runs as of another date, which is how to rehearse the first of next
month; ``--dry-run`` sends nothing.  The command exits non-zero when any email
failed, so the systemd unit goes to ``failed`` rather than reporting a clean run
that reached nobody.  In production ``caldart-reports.timer`` runs it daily at
06:00 (:ref:`deploy-reports`).


Tests
=====

``backend/tests/test_scheduled_reports.py`` covers the schedule over every
cadence, the run on a frozen clock (what is due and nothing else, moving on,
a refused send left due, a report the stored filters no longer build left due,
a recipient who lost the role paused, the recipient's address brought up to
date, both formats), the dry run, two runs at once, the audit line, the command, the timer and the run endpoint.
``backend/tests/test_dart_rosters.py`` covers the roster's due rule across
months and years, ``no_recipients`` and ``no_email``, the attachment, and the
two roster endpoints; ``backend/tests/test_report_subscriptions.py`` the
subscription endpoints and **Send now**.  Both email bodies are compared whole
with ``backend/tests/golden/scheduled-report.txt`` and
``backend/tests/golden/dart-roster.txt``.
