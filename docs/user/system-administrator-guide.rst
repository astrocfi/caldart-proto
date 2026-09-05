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

``system_admin`` passes every permission check in the system.  In practice you
can:

* do everything a member, DART leader, user administrator, account
  administrator and website administrator can do;
* open ``/portal/system``: health, backups, reminders;
* sign in to the Django admin at ``/django-admin/`` if your account is also a
  superuser.

Because it is total, keep it to the one or two people who actually run the
site.  Everyone else should hold the narrower role that matches their job —
``account_admin`` for membership work, ``website_admin`` for pages,
``user_admin`` for accounts and roles.  Roles are assigned under **Users &
roles** in the portal.


The system screen
=================

Sign in and choose **System** in the sidebar, or go straight to
``/portal/system``.  Three panels, top to bottom.


Health
------

Six checks, each with an **OK**, **Warning** or **Attention** chip.  **Refresh**
re-runs them.

**Database**
   Whether the application can reach Postgres.  Anything other than ``ok`` and
   the site is down or about to be; the value is the connection error.  This is
   a server problem — see the deployment guide's troubleshooting section.

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
:doc:`../developer/backup-restore`.


Renewal reminders
-----------------

CalDART emails members five times around their expiry date: 60, 30 and 7 days
before, on the day itself, and 30 days after.  A scheduled job runs every
morning at 07:00 and sends whatever is due, so in normal operation you never
touch this panel.

When you do want to run it by hand:

1. Leave **Dry run (send nothing)** ticked the first time.  It reports what
   *would* go out without sending anything or recording anything.
2. Press **Run now**.  The result reads, for example, "Would send 4 emails,
   skipped 2."  Skipped means already sent, or the member has renewed, or holds
   a lifetime membership, or their account is deactivated.
3. If the numbers look right and you have a reason to send now rather than
   waiting for the morning, clear the checkbox and press **Run now** again.

Running it twice sends nothing twice.  Each member gets one email per
membership per kind, and the log below the button is what enforces that.

The table shows the twenty most recent reminders — when, which kind, which
member, which address — with a filter by kind.  Use it to answer "were they
told?" when somebody says their membership lapsed without warning.  Account
administrators can see this log too.

The wording of the emails and the 07:00 schedule are in
:doc:`../developer/reminders`.


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
Installing or upgrading the application       :doc:`../developer/deployment`
Restoring a backup                            :doc:`../developer/backup-restore`
Changing configuration or secrets             :doc:`../developer/configuration`
Changing the reminder schedule or wording     :doc:`../developer/reminders`
Payment provider keys and webhooks            :doc:`../developer/payments-setup`
============================================  ==================================

The quickest health check from a shell on the server is::

  manage.py health --json

which prints exactly what the health panel shows.


Adding another administrator
============================

Under **Users & roles**, find the person and add the role they need.  Grant
``system_admin`` only to someone who will genuinely run the server; for
membership work ``account_admin`` is enough, and for the website
``website_admin``.

If somebody leaves, deactivate the account rather than deleting it:
deactivation keeps their payment and membership history intact, blocks sign-in
immediately, and stops the reminder emails.
