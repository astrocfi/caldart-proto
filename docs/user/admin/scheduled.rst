:roles: system_admin

===============
Scheduled tasks
===============

**Scheduled tasks** lists the six jobs the server runs on a schedule. You can run each one
by hand here, and each is safe to run twice. All but the bulk email sender have a practice
run that shows what they would do. Only a system administrator sees this page, under
**System** in the menu. In normal running you never need to touch it.

The page has six panels, top to bottom: **Renewal reminder emails**, **Automatic renewal
charges**, **Scheduled reports**, **Year-end statements**, **Bounces**, and **Bulk email
sender**. The first two are easy to confuse. The reminder emails only ever send email. The
renewal charges take the money from members who asked to be renewed automatically. They run
first each morning, so a member they renew doesn't also get a reminder.

Every panel has the same layout, top to bottom. First comes what the job does and when the
server runs it. Next is a line such as *Last run 10/15/2026 at 6:31 AM*, with how that run
ended and **View log**, which opens the job's recent runs and everything each one wrote
(:doc:`job-log`). Then come any fields that shape a run (the **Year**, the **Practice run**
box), **Run now**, and what the last press did. That way **Run now** stays in the same
place, however long the result is. Every panel except the bulk email sender's works like
this:

#. Leave the **Practice run** box checked the first time. A practice run doesn't send,
   charge, or record anything.
#. Press **Run now**. It says *Running…* while the job runs. Below it, a heading says
   **What this run would do**, or **What this run did** after a real run. Under the heading
   are a line of counts and a table naming each email or charge, and the focus moves to the
   heading. If the run didn't find anything to do, it says only *Nothing is due.* (*Nothing
   was due.* after a real run). An empty column is left out, such as **Amount** for emails
   that don't charge anything. **Who** comes first. On a narrow screen, the table drops
   **When**, then **Amount**, and keeps **Who**, **What**, and any **Report or DART** column
   in sight, so a phone still shows which email goes to whom. If that is still too wide, the
   table scrolls sideways, says so above it, and keeps **Who** pinned at the left.
#. If the numbers look right and you have a reason not to wait for the schedule, clear the
   box and press **Run now** again.

Running a job twice never does anything twice, because each job records what it has done.


Renewal reminder emails
=======================

Every morning at 7:00 AM, CalDART emails members whose membership is about to expire or has
just expired. On the default schedule, that is 60, 30, and 7 days before, on the day, and
30 days after. The panel names the days the saved schedule uses. This job only sends email
and never charges anyone. It skips a member whose automatic renewal is on. The
:doc:`reminders` page describes the stages and the subject line of each email.

The box says **Practice run: show what would happen without sending anything**. The result
says, for example, *Would send 4 emails, skipped 2.* If anything was skipped, a line gives
the reasons in the panel's words: *already sent*, *already renewed*, *auto-renew on*,
*lifetime member*, *account deactivated*, and *no address on file*, such as *Skipped:
already sent 10, auto-renew on 2.* If the mail server refused a send, another line says,
for example, *Failed 2.* A refused reminder stays due and goes out on a later run. The
table names every email: **Who** it went to, with their address, **What** reminder it was,
and **When** their membership ends. A reminder doesn't charge anything, so the table
doesn't have an **Amount** column.

Each member gets each reminder once per membership. At the foot of the panel, under the
heading **Reminders sent**, is the same record of recent reminders an account
administrator sees on :doc:`reminders`. Until the first one goes out, it says *No reminders
have been sent yet*, with the days they go.


Reminder schedule
=================

Below the reminder emails, the **Reminder schedule** card sets when they go. It has four
number fields:

- **First reminder**, **Second reminder**, and **Final reminder**: days before a membership
  ends. The defaults are 60, 30, and 7.
- **Lapsed reminder**: days after a membership ends. The default is 30.

The expired reminder doesn't have a number. It goes from the day a membership ends through
the six days after. Change a number and press **Save changes**. *Reminder schedule saved.*
confirms it, and the line under the card shows **Last saved** with the date and your name.
The next morning's run uses the new days. The reminder record, the **Purpose** filter on
:doc:`sent-emails`, and the stage names on :doc:`reminders` all show them too. A member who
has had a reminder never gets the same one again for the same membership. The first
reminder goes at most 180 days ahead, so a member who has just paid for a year never hears
that their membership is running out.

The numbers have to stay in order. If you leave a field empty, it says *Enter a number of
days.* If a number breaks a rule, the rule appears under its field:

- *The first reminder can be at most 180 days before expiry.*
- *The first reminder must be more days before expiry than the second.*
- *The second reminder must be more days before expiry than the final one.*
- *The final reminder must be at least 1 day before expiry.*
- *The lapsed reminder must be 7 to 365 days after expiry.*


Automatic renewal charges
=========================

Members can ask CalDART to renew their membership for them, from a card or PayPal account
saved with the payment service. Every morning at 6:30 AM, before the reminder emails, this
job takes care of them. It emails each member a notice two weeks before their charge
(*CalDART: we will renew your membership on* and the date). It warns anyone whose saved
card runs out before the charge (*the card we renew your membership with expires soon*).
And it takes the charges that are due (*your membership has been renewed*, or *we could not
renew your membership*). The same job charges a life member's recurring donation once a
year, and its emails talk about the donation.

#. Leave **Practice run: show what would happen without charging anything** checked the
   first time. Nobody is charged or emailed.
#. Press **Run now**. The result says, for example, *Would send 2 notices, warn 0, charge 1,
   fail 0, pause 0, and skip 3.* *Notices* counts the two-week notices, and *warn* the members
   whose card runs out first. *Charge* counts the renewals taken, and *fail* the charges the
   payment service declined. *Pause* counts the members whose last try was declined or whose
   membership lapsed too long ago, and *skip* the ones that didn't need anything.
#. Clear the box and press **Run now** again for a real run. It asks first, because it
   charges everybody who is due. Press **Charge what is due**, or **Cancel**. The
   confirmation starts you on **Cancel**, so a second Enter doesn't charge anyone. Escape
   cancels too. The server takes the charges on its own, so the panel says *Running since*
   and the time until they are done, then shows what the run did. Leaving the page doesn't
   stop it. After a real run, the focus moves to the result's heading, as after a practice
   run. If the server couldn't finish a run, the panel says *The renewal run stopped:* and
   the reason, such as *Did not finish.* While a real run is still going, pressing **Run
   now** again gets *An automatic renewal run is already under way.* If the 6:30 AM run
   finds a run under way, it doesn't do anything.

The table names each email and each charge: **Who**, **What** (*Notice*, *Card expiring
warning*, *Charge taken notice*, *Charge failed notice*, or *Charge*), **When**, and
**Amount**. Every scheduled charge records what has already gone out, so a second run never
charges anyone twice. Sometimes the payment service hasn't answered about a charge yet, or
is still processing it. Then the charge counts as neither taken nor declined. The next run
asks about that same charge instead of making another, and counts it as skipped until then.
The member doesn't hear anything until there is an answer. If PayPal may have taken a charge
without saying so, CalDART never charges it again. It waits, counted as skipped, until the
treasurer settles it on the finance **Renewals** tab.

A declined charge is tried again the next day, three days later, and a week after that.
Each time it is declined, the member gets an email with the subject *CalDART: we could not
renew your membership*, or *CalDART: we could not take your recurring donation* for a
recurring donation. After the fourth decline, the automatic renewal turns itself off. That
last email tells the member so, and says the ordinary reminder emails take over. After a
gap, a member whose membership ran out within the last month is renewed on the spot. If it
lapsed longer ago, CalDART doesn't charge them. Their automatic renewal turns itself off,
and they get the same *we could not renew your membership* email.


Scheduled reports
=================

Every morning at 6:00 AM, CalDART sends the emailed reports set up on :doc:`subscriptions`.
Early each month, it also sends each DART's roster. The box says **Practice run: show what
would happen without sending anything**.

The result says, for example, *Would send 5 emails, skipped 1.* If anything was skipped, a
line gives the reasons. *recipient does not have the necessary role* means the recipient
has lost the role that the report needs, and a real run pauses that emailed report. *nobody to send to* means a
DART doesn't have anyone to get its roster. The third reason, *no address on file*, ends it. A
line such as *Failed 1.* counts a refused send or a report that couldn't be built. It stays
due for the next run. The table names each email: *Report* or *Roster*, who it goes to,
and **Report or DART**.


Year-end statements
===================

Each January 15th at 6:45 AM, CalDART emails a statement of gifts to every active member,
friend, and donor who gave in the year before, for their tax return, with the statement
attached. If every gift a person made that year was refunded, they don't get a statement,
since there isn't anything to state. The subject says *CalDART: your 2025 contribution
statement*, with the year and your organization's name.

#. Check the **Year** box; it starts at last year.
#. Leave **Practice run: show what would happen without sending anything** checked the
   first time.
#. Press **Run now**. The result says, for example, *Would send 6, skip 0, and fail 0.*
   *Skip* counts accounts that already got that year's statement. *Fail* counts addresses
   the mail server refused, and accounts without an address.
#. Clear the box and press **Run now** again to send for real.

The table names each *Statement*, the account and its address, and the year's total.


Bounces
=======

Every hour, CalDART reads the mailbox where undeliverable email comes back. Another mail
server may refuse one of its emails for good, because the address doesn't exist or has
stopped taking mail. CalDART then marks that email *Bounced* on :doc:`sent-emails`, and
puts a **Bounced** flag beside the address on the person's member record and user record.
If the other server refused an email for its content or by its own rules, but the address
itself is fine, the email is marked *Bounced* too, but the address isn't flagged. CalDART
ignores delays and temporary failures, which the other server is still retrying. The flag
stays until the address is changed, until the person follows a verification or password
reset link sent to it, or until a user administrator clears it on :doc:`user-record`.

#. Leave **Practice run: show what would happen without changing anything** checked the
   first time. Nothing is marked, and every message stays in the mailbox for the next run.
#. Press **Run now**. The result says, for example, *Would mark 1 bounced, leave 1
   unmatched, ignore 2, and skip 0.* *Bounced* counts the emails matched to a bounce.
   *Unmatched* counts bounces that didn't come back to the return address of an email
   CalDART sent, and these don't change anything. *Ignored* counts the messages that weren't
   a refusal for good. *Skip* counts the messages left unread, because the mail server
   wouldn't hand them over or they were too large to be a bounce.
#. Clear the box and press **Run now** again to mark them for real.

The table names each one: **Who** the email went to, **What** (*Bounced*, or *No matching
email*), the **Report** the other mail server gave, and **When** the email was sent.

If the server doesn't have a bounce mailbox set up, the panel says so as it opens, above
the box: *Bounce checking is off. Ask the person who installed the site to set up a bounce
mailbox.* **Run now** stays unavailable until a mailbox is set up. As the page opens, it
also waits until the server has said whether there is one.


Bulk email sender
=================

Every minute, CalDART starts each bulk email whose time has come, either at the end of its
two minutes to cancel or at the time it was scheduled for. It sends the copies a few at a
time, so the mail service never turns them away. CalDART management writes and sends those
emails on the Bulk email screens (:doc:`../bulk-email/compose`).

The panel doesn't have a practice run, because the sender only sends emails that CalDART
management has already pressed **Send** on. Press **Run now** to run it at once. The page
waits up to 45 seconds, and a larger email carries on in the background after that. The
result says, for example, *Worked on 1 bulk email: sent 37, failed 1, and skipped 4.* If
time ran out, it adds how many copies are still to go, and that the server's sender will
carry on with them within a minute. A table names each copy: **Who** it went to, **What**
(*Sent* or *Failed*), and the **Subject or reason**. If no bulk email was waiting, the panel
says only *Nothing was due.* If the sender was already running, the panel says *The sender
is already running, so this run didn't do anything. Try again in a minute.*


If something looks wrong
========================

A job's emails or charges may stop happening: no reminders on :doc:`reminders` for days, no
scheduled reports, no automatic renewals taken, no statements in January, no bounces marked
for weeks, or bulk emails that stay *Waiting to send*. Look at the panel's last run line and
the job's log (:doc:`job-log`). A failed run gives its reason there. A job that has stopped
running shows as late in the **Scheduled jobs** check on :doc:`health-database`, and the
person who runs the server can look into it. In the meantime, **Run now** does the same
work by hand. On most days a reminder run skips everyone, and that is normal: members got
their email on the first morning they reached each stage. If a run didn't send the mail you
expected, its **Practice run** box is usually still checked. To see whether the emails a
run sent went out, look at :doc:`sent-emails`.
