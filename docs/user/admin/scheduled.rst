:roles: system_admin

=========
Scheduled
=========

**Scheduled** lists the four jobs the server runs on a schedule. Each one can be run by hand
here, and a dry run shows what it would do. Only a system administrator sees it, under
**System** in the menu. In normal running you never need to touch it.

The page has four panels, top to bottom: **Renewal reminder emails**, **Automatic renewal
charges**, **Scheduled reports**, and **Year-end statements**. The first two are a pair that
are easy to confuse. The reminder emails only ever send email. The renewal charges take the
money from members who asked to be renewed automatically, and they run first each morning,
so a member they renew is not also reminded.

Every panel works the same way:

#. Leave the **Dry run** box ticked the first time. A dry run sends, charges, and records
   nothing.
#. Press **Run now**. A heading reads **What this run would do**, or **What this run did**
   after a real run, above a line of counts and a table naming each email or charge.
#. If the numbers look right and you have a reason not to wait for the schedule, clear the
   box and press **Run now** again.

Running any of them twice does nothing twice.


Renewal reminder emails
=======================

Every morning at 07:00 CalDART emails members whose membership is about to expire or has
just expired: 60, 30, and 7 days before, on the day, and 30 days after, on the default
schedule. The panel names the days the stored schedule uses. It sends email only and never
charges anyone. A member whose automatic renewal is on is skipped. The
:doc:`reminders` page describes the stages and the subject line of each email.

The box reads **Dry run (send nothing)**. The result reads, for example, *Would send 4
emails, skipped 2.* When something was skipped, a line gives the reasons in the panel's
words: *already sent*, *already renewed*, *auto-renew on*, *lifetime member*, *account
deactivated*, and *no address on file*, such as *Skipped: already sent 10, auto-renew on 2.*
When the mail server refused a send, a further line reads, for example, *Failed 2.* A
refused reminder stays due and goes out on a later run. The table names every email: **What**
reminder, **Who** it went to with their address, **When** their membership ends, and an
**Amount** column that stays empty for a reminder.

Each member gets each reminder once per membership. Under the panel sits the same record of
recent reminders an account administrator reads on :doc:`reminders`.


Reminder schedule
=================

Beside the reminder emails, the **Reminder schedule** card sets when they go. It has four
number fields:

- **First reminder**, **Second reminder**, and **Final reminder**: days before a membership
  ends. The defaults are 60, 30, and 7.
- **Lapsed reminder**: days after a membership ends. The default is 30.

The expired reminder has no number: it goes from the day a membership ends through the six
days after. Change a number and press **Save**; *Reminder schedule saved.* confirms it, and
the line under the card reads **Last saved** with the date and your name. The next morning's
run uses the new days, and the reminder record, the **Purpose** filter on
:doc:`sent-emails`, and the stage names on :doc:`reminders` all read with them. A member
already sent a reminder is never sent the same one again for the same membership. The first
reminder goes at most 180 days ahead, so a member who has just paid for a year is never told
their membership is running out.

The numbers have to keep their order. A field left empty reads *Enter a number of days.*,
and a refused number shows the rule under its field:

- *The first reminder can be at most 180 days before expiry.*
- *The first reminder must be more days before expiry than the second.*
- *The second reminder must be more days before expiry than the final one.*
- *The final reminder must be at least 1 day before expiry.*
- *The lapsed reminder must be 7 to 365 days after expiry.*


Automatic renewal charges
=========================

Members can ask CalDART to renew their membership for them from a card or PayPal account
saved with the payment provider. Every morning at 06:30, before the reminder emails, this job
looks after them. It emails each member a notice two weeks before their charge (*CalDART: we
will renew your membership on* and the date), warns anyone whose saved card runs out before
the charge (*the card we renew your membership with expires soon*), and takes the charges
that are due (*your membership has been renewed*, or *we could not renew your membership*).
A life member's recurring donation is charged once a year by the same job, and its emails
speak of the donation.

#. Leave **Dry run (charge nothing)** ticked the first time. Nobody is charged or emailed.
#. Press **Run now**. The result reads, for example, *Would notice 2, warn 0, charge 1, fail
   0, pause 0, and skip 3.* *Notice* counts the two-week notices, *warn* the members whose
   card runs out first, *charge* the renewals taken, *fail* the charges the provider
   refused, *pause* the members whose last try was refused or whose membership lapsed too
   long ago, and *skip* those that needed nothing.
#. Clear the box and press **Run now** again for a real run. It asks first, because it
   charges everybody who is due: press **Yes, charge what is due**, or **Cancel**.

The table names each email and each charge: **What** (*Notice*, *Card expiring warning*,
*Charge taken notice*, *Charge failed notice*, or *Charge*), **Who**, **When**, and
**Amount**. Every scheduled charge records what has already gone out, so a second run charges
nobody twice.

A refused charge is tried again the next day, three days later, and a week after that. Each
refusal emails the member with the subject *CalDART: we could not renew your membership*, or
*CalDART: we could not take your recurring donation* for a recurring donation. After the
fourth refusal the automatic renewal turns itself off, and that last email tells the member
so and says the ordinary reminder emails take over. After a gap, a member whose membership
ran out within the last month is renewed on the spot. One lapsed longer is not charged,
their automatic renewal turns itself off, and they get the same *we could not renew your
membership* email.


Scheduled reports
=================

Every morning at 06:00 CalDART sends the report subscriptions set up on :doc:`subscriptions`,
and early each month it sends each DART's roster. The box reads **Dry run (send nothing)**.

The result reads, for example, *Would send 5 emails, skipped 1.* When something was skipped,
a line gives the reasons: *no longer permitted* (the recipient has lost the role that reads
the report, and a real run pauses the subscription), *nobody ticked* (a DART with nobody to
receive its roster), and *no address on file*. A line such as *Failed 1.* counts a refused
send or a report that could not be built; it stays due for the next run. The table names each
email: *Report* or *Roster*, who it goes to, and **Report or DART**.


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

The table names each *Statement*, the account and its address, and the year's total.


If something looks wrong
========================

If a job's emails or charges stop happening (no reminders on :doc:`reminders` for days, no
scheduled reports, no automatic renewals taken, or no statements in January), the server may
have stopped starting that job; the person who runs the server can check it. Meanwhile **Run
now** does the same work by hand. A reminder run that skips everyone is normal on most days,
because members were written to the first morning they reached each stage. A run that sends
nothing when you expected mail usually still has its **Dry run** box ticked. To see whether
the emails a run sent went out, read :doc:`sent-emails`.
