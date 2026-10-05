:roles: system_admin

=========
Scheduled
=========

**Scheduled** lists the six jobs the server runs on a schedule. Each one can be run by hand
here, each is safe to run twice, and all but the bulk email sender have a practice run that
shows what they would do. Only a system administrator sees it, under **System** in the menu.
In normal running you never need to touch it.

The page has six panels, top to bottom: **Renewal reminder emails**, **Automatic renewal
charges**, **Scheduled reports**, **Year-end statements**, **Bounces**, and **Bulk email
sender**. The first two are a pair that
are easy to confuse. The reminder emails only ever send email. The renewal charges take the
money from members who asked to be renewed automatically, and they run first each morning,
so a member they renew is not also reminded.

Every panel is laid out the same way, top to bottom: what the job does and when the server
runs it, any field that shapes a run (the **Year**, the **Practice run** box), **Run now**,
and then what the last run did, so **Run now** stays where it is however long the result.
Every panel but the bulk email sender's works the same way:

#. Leave the **Practice run** box checked the first time. A practice run sends, charges, and
   records nothing.
#. Press **Run now**. It reads *Running…* while the job runs. Below it a heading reads
   **What this run would do**, or **What this run did** after a real run, above a line of
   counts and a table naming each email or charge, and the focus moves to that heading.
   A run that found nothing at all to do says only *Nothing is due.* (*Nothing was due.*
   after a real run). A column no row fills, such as **Amount** for emails that charge
   nothing, is left out. On a narrow screen the table leaves out **When**, then **Amount**,
   then **What**, and keeps **Who** and any **Report or DART** column in sight; on a phone
   it scrolls sideways, says so above it, and keeps **Who** pinned at the left.
#. If the numbers look right and you have a reason not to wait for the schedule, clear the
   box and press **Run now** again.

Running any of them twice does nothing twice: each job records what it has already done.


Renewal reminder emails
=======================

Every morning at 7:00 AM CalDART emails members whose membership is about to expire or has
just expired: 60, 30, and 7 days before, on the day, and 30 days after, on the default
schedule. The panel names the days the stored schedule uses. It sends email only and never
charges anyone. A member whose automatic renewal is on is skipped. The
:doc:`reminders` page describes the stages and the subject line of each email.

The box reads **Practice run: show what would happen, send nothing**. The result reads, for
example, *Would send 4 emails, skipped 2.* When something was skipped, a line gives the
reasons in the panel's
words: *already sent*, *already renewed*, *auto-renew on*, *lifetime member*, *account
deactivated*, and *no address on file*, such as *Skipped: already sent 10, auto-renew on 2.*
When the mail server refused a send, a further line reads, for example, *Failed 2.* A
refused reminder stays due and goes out on a later run. The table names every email: **What**
reminder, **Who** it went to with their address, and **When** their membership ends; a
reminder charges nothing, so the table has no **Amount** column.

Each member gets each reminder once per membership. At the foot of the panel, under its
own heading **Reminders sent**, sits the same record of recent reminders an account
administrator reads on :doc:`reminders`. Before any has gone it reads *No reminders have
been sent yet*, with the days they go.


Reminder schedule
=================

Below the reminder emails, the **Reminder schedule** card sets when they go. It has four
number fields:

- **First reminder**, **Second reminder**, and **Final reminder**: days before a membership
  ends. The defaults are 60, 30, and 7.
- **Lapsed reminder**: days after a membership ends. The default is 30.

The expired reminder has no number: it goes from the day a membership ends through the six
days after. Change a number and press **Save changes**; *Reminder schedule saved.* confirms it, and
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
saved with the payment provider. Every morning at 6:30 AM, before the reminder emails, this job
looks after them. It emails each member a notice two weeks before their charge (*CalDART: we
will renew your membership on* and the date), warns anyone whose saved card runs out before
the charge (*the card we renew your membership with expires soon*), and takes the charges
that are due (*your membership has been renewed*, or *we could not renew your membership*).
A life member's recurring donation is charged once a year by the same job, and its emails
speak of the donation.

#. Leave **Practice run: show what would happen, charge nothing** checked the first time.
   Nobody is charged or emailed.
#. Press **Run now**. The result reads, for example, *Would notice 2, warn 0, charge 1, fail
   0, pause 0, and skip 3.* *Notice* counts the two-week notices, *warn* the members whose
   card runs out first, *charge* the renewals taken, *fail* the charges the provider
   refused, *pause* the members whose last try was refused or whose membership lapsed too
   long ago, and *skip* those that needed nothing.
#. Clear the box and press **Run now** again for a real run. It asks first, because it
   charges everybody who is due: press **Charge what is due**, or **Cancel**, which is
   where the confirmation starts you, so a second Enter charges nobody. Escape cancels
   too. After a real run the focus goes back to **Run now**, with the result below it.

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

Every morning at 6:00 AM CalDART sends the emailed reports set up on :doc:`subscriptions`,
and early each month it sends each DART's roster. The box reads **Practice run: show what
would happen, send nothing**.

The result reads, for example, *Would send 5 emails, skipped 1.* When something was skipped,
a line gives the reasons: *no longer permitted* (the recipient has lost the role that reads
the report, and a real run pauses the emailed report), *nobody to send to* (a DART with nobody to
receive its roster), and *no address on file*. A line such as *Failed 1.* counts a refused
send or a report that could not be built; it stays due for the next run. The table names each
email: *Report* or *Roster*, who it goes to, and **Report or DART**.


Year-end statements
===================

Each January 15th at 6:45 AM CalDART emails every active member, friend, and donor who gave in
the year before a statement of their gifts for their tax return, with the statement attached.
Somebody whose every gift that year was refunded is sent nothing, since there is nothing to
state.
The subject reads *CalDART: your 2025 contribution statement*, with the year and your
organization's name.

#. Check the **Year** box; it starts at last year.
#. Leave **Practice run: show what would happen, send nothing** checked the first time.
#. Press **Run now**. The result reads, for example, *Would send 6, skip 0, and fail 0.*
   *Skip* counts accounts already sent that year's statement, and *fail* an address the mail
   server refused or an account with no address.
#. Clear the box and press **Run now** again to send for real.

The table names each *Statement*, the account and its address, and the year's total.


Bounces
=======

Every hour CalDART reads the mailbox that undeliverable email comes back to. When another
mail server has refused one of its emails for good, because the address does not exist or
no longer takes mail, CalDART marks that email *Bounced* on :doc:`sent-emails` and puts a
**Bounced** flag beside the address on the person's member record and user record. Delays
and temporary failures, which the other server is still retrying, are ignored. The flag stays
until the address is changed, until the person follows a verification or password reset link
sent to it, or until a user administrator clears it on :doc:`user-record`.

#. Leave **Practice run: show what would happen, change nothing** checked the first time.
   Nothing is marked, and every message stays in the mailbox for the next run.
#. Press **Run now**. The result reads, for example, *Would mark 1 bounced, leave 1
   unmatched, ignore 2, and skip 0.* *Bounced* counts the emails matched to a bounce,
   *unmatched* the bounces CalDART could not tie to an email it sent in the last week,
   *ignored* the messages that were not a refusal for good, and *skip* the messages left
   unread because the mail server would not hand them over or they were too large to be a
   bounce.
#. Clear the box and press **Run now** again to mark them for real.

The table names each one: **What** (*Bounced*, or *No matching email*), **Who** the email
went to, the **Report** the other mail server gave, and **When** the email was sent.

If the server has no bounce mailbox set up, the panel says so as it opens, above the box:
*Bounce checking is off. Ask the person who installed the site to set up a bounce
mailbox.* **Run now** is held back until one is set up, and, as the page opens, until the
server has said whether one is.


Bulk email sender
=================

Every minute CalDART starts each bulk email whose time has come, either at the end of its two
minutes to cancel or at the time it was scheduled for, and sends its copies a few at a time,
so the mail provider never turns them away. CalDART management writes and sends those emails
on the Bulk email screens (:doc:`../bulk-email/compose`).

The panel has no practice run, because the sender only sends what CalDART management has
already pressed **Send** on. Press **Run now** to run it at once. The page waits up to 45
seconds; a larger email carries on in the background after that. The result reads, for
example, *Worked on 1 bulk email: sent 37, failed 1, and skipped 4.*, and when the time ran
out it adds how many copies are still to go and that the server's sender carries on with
them within a minute. A table names each copy: **What** (*Sent* or *Failed*), **Who** it
went to, and the **Subject or reason**. When no bulk email was waiting the panel says only
*Nothing was due.* If the sender was already running, the panel says *The sender is
already running, so this run did nothing. Try again in a minute.*


If something looks wrong
========================

If a job's emails or charges stop happening (no reminders on :doc:`reminders` for days, no
scheduled reports, no automatic renewals taken, no statements in January, no bounces
marked for weeks, or bulk emails that stay *Waiting to send*), the server may
have stopped starting that job; the person who runs the server can check it. Meanwhile **Run
now** does the same work by hand. A reminder run that skips everyone is normal on most days,
because members were written to the first morning they reached each stage. A run that sends
nothing when you expected mail usually still has its **Practice run** box checked. To see whether
the emails a run sent went out, read :doc:`sent-emails`.
