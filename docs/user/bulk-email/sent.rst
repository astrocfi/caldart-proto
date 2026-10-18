:roles: management, dart_leader

====
Sent
====

**Sent** lists every bulk email that has gone out, or is going out at the moment, and what
happened to each copy. CalDART management finds it under **Bulk email** in the menu, and sees
every sender's emails. A DART leader opens it too, and sees only their own
(:doc:`dart-leaders`). A system administrator can open it as well.


The list
========

There is one line per email, with the most recently started first, as the arrow on **Date**
shows:

- **Subject**: what it said. A field in it shows as a chip, as on :doc:`compose`. The subject
  opens the email's own page, below.
- **Date**: the day it started sending.
- **Type**: the type of email it was, such as *Operational*.
- **From** and **DART**, for CalDART management only: who sent it, and the DART a DART
  leader's email went to, or a dash for an email that could go to anybody.
- **Status**: a dot and *Sending*, *Sent*, *Stopped*, or *Waiting to send the rest*.
- **Sent**, **Failed**, and **Skipped**: how many copies went out, how many the mail server
  refused, and how many were never sent because the person couldn't receive them. A mission
  callout's counts include its reminders.
- **Actions**, last: **Download results** saves the email's results as a spreadsheet file.
  **Duplicate…** opens the email's own page, where **Duplicate** starts a new draft from it
  (below). On a phone the two buttons sit one above the other.

On a narrow screen, columns drop out one at a time until the rest fit: first **Type**, then
**DART**, and **From**. That keeps the actions in sight. On a phone, the table scrolls
sideways, a note above it says so, and the subject stays pinned at the left. Until the first
send, the table says *No bulk email has been sent* and *Each bulk email appears here once it
starts going out.* A DART leader's table says *You have not sent an email yet* and *Emails you
send appear here once they start going out.* Either one offers **New email**, which opens
:doc:`compose`, to anybody who has people to send to. If a DART leader's profile doesn't name
a DART, a box above the table tells them to set their DART on My profile
(:doc:`dart-leaders`). The list keeps itself up to date while an email is sending.

While an email is sending, its line offers **Stop…** instead of the download. A stopped email
offers **Send the rest…**. Each one opens the email's own page, where the action asks first.


One email's page
================

Under its subject, the page of one sent email says who sent it and when, such as *Sent by
Grace Holloway on 10/03/2026 at 5:34 PM.* It has three cards:

- **Sending progress**: while the email sends, the card shows *Sending… 12 of 38 sent, about
  1 minute left.* with a bar and **Stop sending**. **Stop sending**, then **Stop now**, stops
  it after the copy going out at that moment. Copies already sent can't be called back. When
  it is finished, a line says, for example, *Sent to 37 people. 1 failed and 4 were skipped.*
  (a count of zero is left out), or *Everyone was sent a copy.* Once copies have bounced, *2
  came back undelivered.* follows (`The delivery report`_). A stopped email says *Stopped by*
  and who stopped it, with **Send the rest**. Press it, then **Send them now**, to send the
  email to everybody the stop held back. Each of them is checked again first, as **Retry
  failed** does (below). Anybody who can't receive it any more is marked *Skipped*, with the
  reason. Nobody gets it twice. It starts within a minute, and until then the email says
  *Waiting to send the rest*, with **Stop sending**. A mission callout adds *This is a mission
  callout.* with **See who can fly**, which opens its answers on :doc:`callouts`.
- **The message**: the email as it was sent, with the subject at its head. Above it are its
  type and *Replies go to:* with the address for replies its copies carried. A field shows in
  the subject and the message as the chip you wrote it with, such as *First name, or friend*,
  because each person's copy had their own details filled in. Under the message, a line says
  whether the people it went to can read it again under **Email to me**, with **Hide from
  Email to me** or **Show in Email to me** (`Email to me`_).
- **Who received it**: the delivery report, described next.


The delivery report
===================

**Who received it** shows what happened to every copy, including after it left CalDART.

At its top are the counts: **Sent**, **Failed**, **Skipped**, **Bounced**, and **Retried**.
**Sent** is the number in the line above, *Sent to 37 people*. It counts every copy the mail
server took, including those that came back later. **Bounced** says how many of those came
back. Under the counts is **Retry failed** (below).

Then there is one line for each person on the recipient list, for their first copy. Each line
has **Name**, **Result**, **Email**, **Reason** (in full, on as many lines as it needs),
**Tried at** (such as *10/03/2026 at 5:34 PM*), **Kind**, **DART**, and last **Copy**. On a
narrow screen, **DART**, then **Kind**, **Tried at**, and **Email** drop out. On a phone, the
result wraps so **Copy** stays in sight. **Result** narrows the table to one result, such as
*Failed*, or **Any result** for everybody. **Find a person** narrows it to a name or address.
The table's caption then says how many people it shows out of everybody, such as *Showing 2
of 39*. **Reset filters** clears both. When nobody matches them, the empty table offers its
own **Reset filters** button. **Download results** saves the whole table as a spreadsheet
file, with each person's result, reason, and the time their copy was tried.

Each **Result** means:

- *Sent*: CalDART handed the copy to the mail server.
- *Failed*: the mail server refused it. The reason says *Refused by the mail server*, or
  *Temporarily refused, gave up after 3 retries* when the server asked CalDART to wait and
  then kept refusing.
- *Skipped*: the person couldn't receive it, for the reason given, such as *Address
  bounced*. The reasons are listed on :doc:`compose`.
- *Not sent (stopped)*: the email was stopped before this copy went. The reason names who
  stopped it.
- *Bounced*: CalDART handed the copy to the mail server, but the person's own mail server
  later sent it back as undeliverable. The reason is what that server said, such as
  *5.1.1 550 User unknown*. CalDART checks for these every hour, so a copy can turn from
  *Sent* to *Bounced* a while after the email went out, and the counts change with it.
- *Not sent yet*: the copy is waiting its turn while the email sends.

Seeing one person's copy
------------------------

On the line of anybody whose copy was tried, **View copy** opens that person's copy exactly
as it went, in a window over the page. It shows who it went to and when, its subject, and the
email itself, with the details filled in for them at the time, even if they have changed
their profile since. This answers "what did I get?" Its links open in a new tab. The
unsubscribe link at its foot is shown, but it doesn't do anything here, since it belongs to
the person the copy went to. The page behind waits until you close the window. **Close**, or
the Escape key, closes it and takes you back to the line you opened it from. If somebody was
skipped, or hasn't been sent a copy yet, there isn't a copy to view.

Retry failed
------------

When the mail server refused some copies, **Retry failed** sends a fresh copy to only those
people, once you press **Retry now**. Nobody who was already sent a copy gets another. For a
mission callout, a failed copy of any round is retried, but anybody a later round reached
doesn't get an earlier one again. Nobody whose copy bounced (their address is bad) or who was
skipped is sent one. Each person is checked again first, as for any send. A person is marked
*Skipped*, with the reason, if their account has since been deleted or deactivated, their
address has bounced, or they have turned this type of email off. On a DART leader's email,
so is anybody who has left the leader's DART. If a user administrator has corrected an
address since, the fresh copy goes to the corrected one. The copies start going within a
minute, and the page shows their progress as for any send. The message says *The failed
copies will be sent again within a minute.* If everybody whose copy failed is skipped this
way, nothing is sent, and the page says *Nobody whose copy failed can be sent one now.*

**Retry failed** can't be pressed when no copy failed, and it says so. On a stopped email, it
says to send the rest first: press **Send the rest**, and once that has finished, retry the
failed copies. Each retry is listed under **Retries** at the bottom of the report, with when
it was pressed, who pressed it, and how many people it sent a fresh copy to.


Email to me
===========

Every person a bulk email went to can read it again on their own **Email to me** page, and
every copy ends with a *View this email in your browser* link to it there. Each person sees
only their own copy.

To take an email off everybody's **Email to me**, for example a call for volunteers that has
been filled, press **Hide from Email to me** under the message, then **Hide it**. The line
under the message then says the email is hidden. The people it went to don't see it under
**Email to me** any more, and the link in their copy doesn't open it. Nothing else changes:
this page, its counts, and its results stay as they are. **Show in Email to me** puts it back
at once. Only CalDART management sees these buttons. Each copy also appears in the log of sent
emails as *Bulk email*.


Duplicate
=========

**Duplicate**, on the email's own page under **Sending progress**, starts a new draft of your
own from the email. **Duplicate…** on each line of the list opens that page. It asks how to
copy:

- **Copy the message**: the new draft has the email's subject, message (pictures included),
  type, and address for replies, and an empty recipient list.
- **Copy the message and the people**: the recipient list also has everybody the email was
  for, as their accounts are today. CalDART works out again whether each person receives the
  new email. Somebody who has since turned that type of email off, or whose address bounced,
  shows as skipped. On the recipient list, **Chosen by** says *Copied from* and the subject.
  Accounts deleted since are left out. A DART leader's copy goes only to their own DART, and
  anybody outside it shows as skipped, *Not in your DART*.

The new draft opens on :doc:`compose`, ready to change and send, with a line at the top
saying which email it is a copy of. The email you copied stays as it was. A copy of a
mission callout is a callout too. It starts without any answers, and its answers close two
days ahead (:doc:`callouts`). **Cancel** closes the question without copying anything.


If something looks wrong
========================

If somebody says the email never arrived, find their row. *Sent* means CalDART handed the
copy to the mail server, so ask them to check their spam folder, or point them to their
**Email to me** page, where they can read it. *Failed*, *Bounced*, or *Skipped* gives the
reason. After a failure the mail server reported, **Retry failed** may get the copy through.
A user administrator or an account administrator corrects an address on the person's account.
If many people find CalDART's email in their spam folders, ask a system administrator to read
**Mail delivery** on :doc:`../admin/health-database`. To write to everybody again, use
**Duplicate** with the people. To write only to the people a failure left out, download the
results and add them to a new email.
