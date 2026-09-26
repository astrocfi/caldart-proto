======
System
======

**System** shows how the server is doing, the database backups it holds, and the four jobs
it runs on a schedule: the renewal reminders, the scheduled reports, the automatic renewals,
and the year-end statements. It also holds the email log, the record of every email CalDART
has tried to send. Only a system administrator sees it, under **System** in the menu.

A system administrator can do everything any other role can do. Keep the role to the one or
two people who run the site, and give everyone else the narrower role that fits their job on
the :doc:`user-record`. Anything that has to happen on the server itself, such as installing
an upgrade, restoring a backup, or changing the settings, is a job for the person who
installed the site.

The page has seven panels, top to bottom: **Health**, **Backups**, **Renewal reminders**,
**Email log**, **Scheduled reports**, **Automatic renewals**, and **Year-end statements**.


Health
======

Six checks, each with a value and an **OK**, **Warning**, or **Attention** chip. **Refresh**
runs them again.

- **Database**: whether the site can reach its database. Anything but *ok* means the site is
  down or about to be. Tell whoever runs the server at once.
- **Pending migrations**: changes to the database that arrived with an upgrade and have not
  been applied. It should read 0. Anything else means an upgrade was left half finished.
- **Disk free**: the space left where backups are kept. It warns below 2,048 MB and asks for
  attention below 512 MB. Old backups are the usual reason; download the ones worth keeping
  and ask for the rest to be deleted from the server.
- **Last backup**: when the newest backup was taken. It warns after a week, and asks for
  attention after a month or when there has never been one. Take one from the next panel.
- **Version**: which release is running. Quote it when you report a problem.
- **Debug mode**: must read *off*. If a live site reads *on*, have it fixed at once, because
  it shows internal details to anyone who causes an error.


Backups
=======

The table lists every backup on the server, newest first, with its **File** name, when it
was **Taken**, its **Size**, and a **Download** link.

**Create backup** takes one now. The button reads *Taking a backup…* while it works, which
takes a minute or two on a large database, so leave the page open. A message names the file
when it is done.

**Download** saves a backup to your own computer. Keep at least one copy somewhere other than
the server: a backup on the same disk as the database is lost with it. Take a backup before
every upgrade, before any bulk change, and before anyone experiments with the data.

There is no restore button. Restoring replaces everything in the database and is done on the
server with the site stopped, by the person who installed it.


Renewal reminders
=================

Every morning at 07:00 CalDART emails members whose membership is near its end or has just
ended, at five stages. The :doc:`reminders` page describes the stages and the subject line of
each email. In normal running you never touch this panel. To send them by hand:

#. Leave **Dry run (send nothing)** ticked the first time. A dry run sends and records
   nothing.
#. Press **Run now**. A heading reads **What this run would do**, or **What this run did**
   after a real run, and a line such as *Would send 4 emails, skipped 2.* follows.
#. If the numbers look right and you have a reason not to wait for the morning, clear the box
   and press **Run now** again.

When something was skipped, a line gives the reasons in the panel's words: *already sent*,
*already renewed*, *auto-renew on*, *lifetime member*, *account deactivated*, and *no address
on file*, such as *Skipped: already sent 10, auto-renew on 2.* When the mail server refused
a send, a further line reads, for example, *Failed 2.* A refused reminder stays due and goes
out on a later run. A table then names every email: **What** reminder, **Who** it went to
with their address, **When** their membership ends, and an **Amount** column that stays empty
for a reminder.

Running it twice sends nothing twice: each member gets one email per membership at each
stage. Under the panel sits the same record of recent reminders an account administrator
reads on :doc:`reminders`.


Email log
=========

The email log lists every email CalDART has tried to send, 25 at a time and newest first.
It answers "what did we send this person?" and "is our mail going out at all?"

- **Sent**: the date and time. Click the heading to turn the order round.
- **Purpose**: what the email was for.
- **To**: the recipient's name, when CalDART knows it, and the address. A DART contact on a
  roster has a name and no account.
- **Status**: *Sent*, or *Failed:* and the reason the mail server gave.
- **Attachments**: the names of any files attached, such as a report or a statement.

When there are more than 25 emails, the foot reads, for example, *Showing 1–25 of 412*, with
**Previous** and **Next**. The filters narrow the whole log, every page of it:

**Purpose**
   One kind of email: *Renewal reminder (60 days)*, *Renewal reminder (30 days)*, *Renewal
   reminder (7 days)*, *Renewal reminder (expired)*, *Renewal reminder (30 days after)*,
   *Renewal turned on*, *Renewal notice*, *Card expiring*, *Renewal charged*, *Renewal
   declined*, *Renewal turned off*, *Receipt*, *Refund*, *Contribution statement*,
   *Invitation*, *Password reset*, *Email verification*, *Scheduled report*, or *DART
   roster*.
**Status**
   **Sent** or **Failed**.
**From** and **To**
   A range of days, both included.
**Search**
   A name or an address, including somebody with no account.

**Reset to Defaults** clears the filters. The filters, the order, and the page are kept in
the page's address, so a filtered view can be bookmarked or sent to another system
administrator.

**Export CSV** and **Export PDF** download every email the filters match, in the table's
order. They carry **Sent**, **Purpose**, **To**, **Name**, **Subject**, and **Status**
unless you choose others with **Columns**; **Error** and **Attachments** are off until you
tick them. **Load columns** and **Save columns** keep a set of columns under a name, as
:ref:`saved-column-sets` describes.

The log does not prove delivery: a mail server that accepts an email and bounces it an hour
later leaves a row marked *Sent*. Only a system administrator sees the log, because it lists
every address the site has written to.


Scheduled reports
=================

Every morning at 06:00 CalDART sends the report subscriptions set up on :doc:`reports`, and
early each month it sends each DART's roster. This panel sends them by hand and works like the
reminders panel: leave **Dry run (send nothing)** ticked, press **Run now**, read the result,
then clear the box and press **Run now** again to send for real.

The result reads, for example, *Would send 5 emails, skipped 1.* When something was skipped,
a line gives the reasons: *no longer permitted* (the recipient has lost the role that reads
the report, and a real run pauses the subscription), *nobody ticked* (a DART with nobody to
receive its roster), and *no address on file*. A line such as *Failed 1.* counts a refused
send or a report that could not be built; it stays due for the next run. The table names each
email: *Report* or *Roster*, who it goes to, and **Report or DART**. Running it twice sends
nothing twice.


Automatic renewals
==================

Members can ask CalDART to renew their membership for them from a card or PayPal account
saved with the payment provider. Every morning at 06:30, before the reminders, a job looks
after them. It emails each member a fortnight before their charge (*CalDART: we will renew
your membership on* and the date), warns anyone whose saved card runs out before the charge
(*the card we renew your membership with expires soon*), and takes the charges that are due
(*your membership has been renewed*, or *we could not renew your membership*). A life
member's recurring donation is charged once a year by the same job, and its emails speak of
the donation.

This panel runs the same job by hand:

#. Leave **Dry run (charge nothing)** ticked the first time. Nobody is charged or emailed.
#. Press **Run now**. The result reads, for example, *Would notice 2, warn 0, charge 1, fail
   0, pause 0, and skip 3.* *Notice* counts the fortnight's warnings, *warn* the members
   whose card runs out first, *charge* the renewals taken, *fail* the charges the provider
   refused, *pause* the members whose last try was refused or whose membership lapsed too
   long ago, and *skip* those that needed nothing.
#. Clear the box and press **Run now** again for a real run. It asks first, because it charges
   everybody who is due: press **Yes, charge what is due**, or **Cancel**.

The table names each email and each charge: **What** (*Notice*, *Card expiring warning*,
*Charge taken notice*, *Charge failed notice*, or *Charge*), **Who**, **When**, and
**Amount**. Running it twice charges nobody twice.

A refused charge is tried again the next day, three days later, and a week after that. Each
refusal emails the member with the subject *CalDART: we could not renew your membership*, or
*CalDART: we could not take your recurring donation* for a recurring donation. After the
fourth refusal the automatic renewal turns itself off, and that last email tells the member
so and says the ordinary reminders take over. After a gap, a member whose membership ran out
within the last month is renewed on the spot. One lapsed longer is not charged, their
automatic renewal turns itself off, and they get the same *we could not renew your
membership* email.


Year-end statements
===================

Each January 15th at 06:45 CalDART emails every active member, friend, and donor who gave in
the year before a statement of their gifts for their tax return, with the statement attached.
The subject reads *CalDART: your 2025 contribution statement*, with the year and your
organization's name.

#. Check the **Year** box; it starts at last year.
#. Leave **Dry run (send nothing)** ticked the first time.
#. Press **Run now**. The result reads, for example, *Would send 6, skip 0, and fail 0.*
   *Skip* counts accounts already sent that year's statement, and *fail* an address the mail
   server refused or an account with no address.
#. Clear the box and press **Run now** again to send for real.

The table names each *Statement*, the account and its address, and the year's total. Running
it twice for a year sends nothing twice.


Routine
=======

Once a week, open **System**: six **OK** chips and a recent backup are the whole check. Before
any upgrade, take a backup and download it. Once a month, keep a copy somewhere off the
server. When someone reports a problem, read **Health** first and note the **Version**.


If something looks wrong
========================

If **Create backup** fails, the message under it comes from the server; pass it to whoever
runs the server, since nothing half written is left behind. If a job's emails or charges stop
happening (no reminders on :doc:`reminders` for days, no scheduled reports, no automatic
renewals taken, or no statements in January), the timer that starts that job each morning
may have stopped: each of the four jobs has its own, and the person who runs the server can
check it. Meanwhile **Run now** does the same work by hand. A reminder run that skips everyone
is normal on most days, because members were written to the first morning they reached each
stage. A run that sends nothing when you expected mail usually still has its **Dry run** box
ticked. If the email log shows many *Failed:* rows, the site cannot reach its mail server;
a password reset to your own address is a quick test once it is fixed.
