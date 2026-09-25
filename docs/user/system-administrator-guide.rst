==========================
System administrator guide
==========================

You hold the ``system_admin`` role, which means everything: every member and
payment screen, the Wagtail admin, and one screen nobody else can see —
``/portal/system``, where you check the server's health, take database backups
and run the renewal reminders.

This guide covers that screen and the routine around it.  Anything that has to
happen on the server itself — installing an upgrade, restoring a backup,
changing configuration — is in the developer guide, and this page says when to
go there.


What the role grants
====================

``system_admin`` passes every role check in the system.  The one thing it
cannot do is complete another member's checkout: only the member who started a
payment can confirm it.  In practice you can:

* do everything a member, DART leader, user administrator, account
  administrator and website administrator can do;
* open ``/portal/system``: health, backups, reminders;
* sign in to the Django admin at ``/django-admin/`` — granting ``system_admin``
  in the portal also sets the account's Django superuser flag, and that flag is
  what opens the door.

Because it is total, keep it to the one or two people who actually run the
site.  Everyone else should hold the narrower role that matches their job —
``account_admin`` for membership work, ``website_admin`` for pages,
``user_admin`` for accounts and roles.  Grant roles under **Users & roles** in
the portal, never by editing an account's groups in the Django admin's
**Permissions** fieldset: only the portal keeps the Django superuser and staff
flags in step with the roles it writes, so a ``system_admin`` group added by
hand there leaves the superuser flag off and the account locked out of
``/django-admin/``.


The system screen
=================

Sign in and choose **System** in the sidebar, or go straight to
``/portal/system``.  Three panels, top to bottom.


Health
------

Six checks, each with an **OK**, **Warning**, or **Attention** chip.  **Refresh**
re-runs them.

**Database**
   Whether the application can reach Postgres.  Anything other than ``ok`` and
   the site is down or about to be; the value is the connection error.  This is
   a server problem — see :ref:`deploy-troubleshooting`.

**Pending migrations**
   Database changes that shipped with the code but have not been applied.
   Should be ``0``.  Anything else means an upgrade was left half-finished;
   somebody needs to run ``manage.py migrate`` on the server.

**Disk free**
   Free space where backups are written.  Warns below 2 GB, fails below
   512 MB.  Old dumps are the usual culprit — nothing deletes them
   automatically.  Download the ones worth keeping, delete the rest on the
   server.

**Last backup**
   When the newest dump was taken.  Warns after a week, fails after a month or
   if there has never been one.  If it is red, take one now with the button in
   the next panel.

**Version**
   Which release is running.  Worth quoting when reporting a problem.

**Debug mode**
   Must be ``off``.  If a production site says ``on``, stop and fix it: debug
   mode shows internal details, including parts of the configuration, to
   anyone who triggers an error.


Backups
-------

The list is every dump on the server, newest first, with its size and the date
it was taken.  Columns sort.

**Create backup** takes one now.  The button says "Taking a backup…" while
``pg_dump`` runs — on a large database that is a minute or two, so leave the
tab open — and a toast confirms the file name when it lands.

**Download** saves a dump to your own machine.  Do that before anything risky,
and keep at least one copy somewhere other than the server: a backup on the
same disk as the database is not a backup.

Take one before every upgrade, before a bulk import or deletion, and before
anyone experiments with the data.  It costs a minute and it is the only thing
standing between a mistake and a rebuilt membership list.

There is no restore button, deliberately.  Restoring wipes the current database
and is a command-line job with the site stopped; see
:doc:`/developer/backup-restore`.


Renewal reminders
-----------------

CalDART emails members at five stages around their expiry date.  Each stage
covers a stretch of the calendar rather than one day, so every member passes
through it: **60 days** reaches anyone expiring in 31 to 60 days, **30 days**
anyone expiring in 8 to 30 days, **7 days** anyone expiring within the week,
**expired** anyone whose term ran out in the last seven days, and **30 days
after** anyone whose term ran out between 30 and 60 days ago.  Each member gets
each stage once.  A scheduled job runs every morning at 07:00 and sends whatever
is due, so in normal operation you never touch this panel.

When you do want to run it by hand:

1. Leave **Dry run (send nothing)** ticked the first time.  It reports what
   *would* go out without sending anything or recording anything.
2. Press **Run now**.  The result reads, for example, "Would send 4 emails,
   skipped 2."  Skipped means already sent, or the member has renewed, or their
   membership renews itself, or they hold a lifetime membership, or their
   account is deactivated, or there is no address on file.
3. If the numbers look right and you have a reason to send now rather than
   waiting for the morning, clear the checkbox and press **Run now** again.

Underneath the result, a table headed **What a live run would do** after a
rehearsal, or **What this run did** after a real one, names every action
behind those numbers: which reminder, the member and their address, the day
their term runs out, and the amount — always empty here, since a reminder
moves no money.  It is empty when nothing was due.

A rehearsal on the server says the same thing on a shell.  ``caldart_manage
send_renewal_reminders --dry-run`` prints one line per member under the counts --
which reminder, who they are, their address, and the day their term runs out --
so somebody with a shell can read off exactly who a live run would write to
(:doc:`/developer/reminders`).

Running it twice sends nothing twice.  Each member gets one email per
membership per kind, and the log below the button is what enforces that.

The table shows the twenty most recent reminders — when, which kind, which
member, which address — with a filter by kind.  Use it to answer "were they
told?" when somebody says their membership lapsed without warning.  Account
administrators read the same log on their own **Reminders** screen, without
the run controls (:doc:`account-administrator-guide`).

A run the timer missed costs nothing: because the stages are stretches of the
calendar, the next morning's run finds everybody the missed one would have.  Only
a gap of a week or more can let a member pass through the 7-day or expired stage
unheard.  The wording of the emails and the 07:00 schedule are in
:doc:`/developer/reminders`.

Automatic renewals
------------------

Members can ask CalDART to renew their membership for them, from a card or
PayPal account saved with the payment provider.  A second scheduled job runs
every morning at 06:30 — half an hour before the reminders, so a membership it
renews is never also nagged about — and does three things: it schedules the
charge for each membership running out and emails the member a fortnight's
warning, it warns anyone whose saved card expires before their next charge, and
it charges whatever is due.

A life member's standing authority is a contribution rather than a renewal: it
charges once a year, on the anniversary of the day it was set up or of the last
contribution taken, and extends no membership term.  The same scan handles it,
and its emails say "contribution" throughout.

The **Renewals** panel runs the same scan by hand, and works like the reminders
one:

1. Leave **Dry run (charge nothing)** ticked the first time.  It reports what
   *would* happen without charging anybody, emailing anybody or writing
   anything.
2. Press **Run now**.  The result reads, for example, "Would notice 2, warn 0,
   charge 1, fail 0, pause 0, and skip 3", and a real run says the same in the
   past tense.  *Noticed* is the fortnight's-warning emails, *warned* the
   members whose saved card expires before their next charge,
   *charged* the renewals taken, *failed* the charges a provider refused,
   *paused* the members whose last retry was refused, or whose membership had
   lapsed too long to catch up, and whose automatic renewal has therefore
   switched itself off, and *skipped* the ones that needed nothing doing.
3. If the numbers look right and you have a reason to run now rather than
   waiting for the morning, clear the checkbox and press **Run now** again.
   A real run asks before it starts, because it charges every member whose
   renewal is due: press **Yes, charge what is due** to go ahead, or
   **Cancel** to think again.

Underneath the result, a table headed **What a live run would do** after a
rehearsal, or **What this run did** after a real one, names every email and
every charge behind those numbers: what it was, the member and their
address, when, and how much.  It is empty when nothing was due.

Here too a rehearsal on the server names the people behind the numbers.
``caldart_manage run_auto_renewals --dry-run`` prints one line per email it would
send and per charge it would take -- what, who, when, and how much.  A rehearsal
cannot ask the provider whether a charge would go through, so it lists the charge
and the message a charge that succeeds sends; a live run lists the decline
instead when a provider refuses (:doc:`/developer/renewals`).

Running it twice charges nobody twice, and sends nothing twice: each scheduled
charge records what has already gone out.

A refused charge is not an outage.  CalDART tries again the next day, three days
later, and a week after that; only when all four attempts are refused does it
stop, tell the member, and hand them back to the ordinary reminders.  A treasurer
or an account administrator reads the same renewals on
**Administration → Payments**, with the reason each refusal was given.

If the scan has not run for a while, the next run catches up: a member whose
membership ran out within the last month is renewed on the spot, and told the
charge is happening that day.  A member who has been lapsed longer than that is
not charged unannounced — their automatic renewal switches itself off, they are
told why, and the ordinary reminders resume.

What it charges, when, and how to change the schedule are in
:doc:`/developer/renewals`.

Email log
---------

CalDART records every email it sends -- renewal reminders, the automatic-renewal
notices, receipts, refund notices, invitations, and password links -- with the
address it went to, the member it concerned, the subject, whether the mail server
took it, and any file attached.  It is the answer to "what did we actually send
this person?", and to "is our mail going out at all?": a message a mail server
refused is on the list, marked failed, with the error beside it.

Two things it is not.  It is not delivery confirmation: a mail server that takes
a message and bounces it an hour later leaves a message marked sent.  And it is
not the reminder log above, which exists to stop a member being sent the same
reminder twice; the email log is the record of the message itself.

Only a system administrator sees it, because it lists every address the
installation has written to.  An account administrator answering "was this member
told?" uses the **Reminders** screen instead.  The rows are also readable through
``GET /system/emails``, described in :doc:`/developer/api-system`, and in the
Django admin under **Mail**, where they cannot be edited.


Routine
=======

**Weekly**
   Open ``/portal/system``.  Six green chips and a recent backup is the whole
   check.

**Before any upgrade**
   Take a backup and download it.

**Monthly**
   Download a dump and put it somewhere off the server.  Delete dumps older
   than your retention window so the disk does not fill.

**When someone reports a problem**
   Check the health panel first; it distinguishes "the server is unwell" from
   "this one screen is wrong".  Note the version before reporting it.


When to go to the server
========================

These are the jobs that cannot be done from the portal, all documented in the
developer guide:

============================================  ==================================
Job                                           Where
============================================  ==================================
Installing or upgrading the application       :doc:`/developer/deployment`
Restoring a backup                            :doc:`/developer/backup-restore`
Changing configuration or secrets             :doc:`/developer/configuration`
Changing the reminder schedule or wording     :doc:`/developer/reminders`
Payment provider keys and webhooks            :doc:`/developer/payments-setup`
============================================  ==================================

The quickest health check from a shell on the server is, using
``caldart_manage`` from :ref:`deploy-manage-commands`::

  caldart_manage health --json

which prints exactly what the health panel shows, for example::

  {
    "db": "ok",
    "pending_migrations": 0,
    "disk_free_mb": 48213,
    "last_backup": "2026-09-20T07:00:04-07:00",
    "version": "0.1.0",
    "debug": false
  }

The command's own exit status is always ``0``, even when a field above reads
badly — read the JSON, do not script against the exit code.


Adding another administrator
============================

Under **Users & roles**, find the person and add the role they need.  Grant
``system_admin`` only to someone who will genuinely run the server; for
membership work ``account_admin`` is enough, and for the website
``website_admin``.

If somebody leaves, deactivate the account rather than deleting it:
deactivation keeps their payment and membership history intact, blocks sign-in
immediately, and stops the reminder emails.


When something goes wrong
=========================

**Create backup fails with "Neither pg_dump nor docker is available".**
   The application is looking for a way to reach PostgreSQL and finding
   neither.  Install ``postgresql-client`` on the server, or — in development
   — start the compose stack with ``make up``, and try again.  Nothing is
   written when it fails, so there is no half-finished dump to clean up.

**Create backup fails with a message from ``pg_dump`` itself.**
   The panel shows whatever ``pg_dump`` wrote to standard error, which is
   usually a permission or authentication problem.  Fix it at the database and
   retry; the same command run from a shell on the server (``manage.py
   db_backup``) gives you the fuller output.

**The backup list is empty even though backups exist.**
   The panel reads one directory — the one named by ``BACKUP_DIR``.  A dump
   somebody wrote elsewhere is not listed and is not downloadable.  See
   :doc:`/developer/configuration`.

**A backup download 404s.**
   Only a plain file name ending ``.sql.gz`` inside ``BACKUP_DIR`` can be
   downloaded — starting with a letter or digit, then any run of letters,
   digits, ``.``, ``_`` or ``-``.  The automatic ``caldart-<timestamp>.sql.gz``
   names always fit.  A name you chose yourself may not: ``db_backup --name``
   writes whatever name you give it without checking, so a dump called
   ``nightly backup.sql.gz`` or ``_snapshot.sql.gz`` is listed and then refused
   at download, and one that does not end ``.sql.gz`` at all is never listed.
   The check is deliberately strict: a name outside that pattern, or one
   reached through a symbolic link out of the directory, is refused rather than
   served.  Rename it to fit, or copy it off the server directly.

**Health says migrations are pending.**
   Code has been deployed without ``manage.py migrate``.  Until it runs, the
   database and the application disagree about the schema; do it now.  See
   :doc:`/developer/deployment`.

**Health says the last backup is old, or missing.**
   Backups are on demand in this prototype — there is no timer for them, only
   for the reminder scan.  Take one from the panel, and consider adding a
   scheduled job.

**A reminder run reports everything skipped.**
   That is the normal answer most days: the members in each stage were written
   to the first morning they entered it, and every run after that finds them
   already told.  The summary breaks the skips down by reason —
   ``already_sent``, ``lifetime``, ``renewed``, ``auto_renew``,
   ``inactive_user``, ``no_email``.  ``already_sent`` is the common one and
   means an earlier run in that stage already sent it.

**A reminder run sends nothing when you expected mail.**
   Check that **Dry run** is unticked: it is ticked by default, and a dry run
   writes nothing, sends nothing and flips no statuses.

**Members say reminders never arrive.**
   The scan is only as reliable as the timer that drives it.  Confirm
   ``caldart-reminders.timer`` is enabled and running on the server, and then
   that mail is leaving it at all — a password reset is the quickest test.
   ``systemctl status caldart-reminders`` reads ``failed`` when the last run
   could not send something, and ``journalctl -u caldart-reminders`` names the
   member and membership ids it could not reach.

The quickest diagnosis from a shell on the server is ``caldart_manage
health``, or ``caldart_manage health --json`` if you want to feed it to
something else; see :ref:`deploy-manage-commands`.
