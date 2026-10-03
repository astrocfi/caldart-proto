:roles: management, dart_leader

====
Sent
====

**Sent** lists every bulk email that has gone out, or is going out now, and what became of
each copy. CalDART management opens it as **Sent** under **Bulk Email** in the menu, and sees
every sender's emails. A DART leader opens it too, and sees only their own
(:doc:`dart-leaders`). A system administrator can open it as well.


The list
========

One line per email, the most recently started first:

- **Subject**: what it said. It opens the email's own page, below.
- **Type**: the kind of email it was, such as *Operational*.
- **Date**: the day it started sending.
- **From** and **DART**, for CalDART management only: who sent it, and the DART a DART
  leader's email went to, or a dash for an email that could go to anybody.
- **Status**: a dot and *Sending*, *Sent*, *Stopped*, or *Waiting to send the rest*.
- **Sent**, **Failed**, and **Skipped**: how many copies went, were refused by the mail
  server, and were never sent because the person could not receive them.
- **Download results** saves the email's results as a spreadsheet file.

Before the first send the table reads *No bulk email has been sent*. The list keeps itself up
to date while an email is sending. On a narrow screen the table scrolls sideways.

An email that is sending offers **Stop…** in place of the download, and a stopped one **Send
the rest…**. Each opens the email's own page, where the action asks first.


One email's page
================

The page of one sent email has three cards:

- **Where it stands**: while it sends, *Sending… 12 of 38 sent, about 1 minute left.* with a
  bar and **Stop sending**, which stops it after the copy going out now, once you press
  **Stop now**; copies already sent cannot be called back. When it is finished, a line such
  as *Sent to 37 people. 1 failed and 4 were skipped.*, or *Everyone was sent a copy.*,
  followed by *2 came back undelivered.* once copies have bounced (`The delivery report`_). A
  stopped email reads *Stopped by* who stopped it, with **Send the rest**, which sends it to
  everybody the stop kept it from once you press **Send them now**. Nobody gets it twice, it
  starts within a minute, and the email reads *Waiting to send the rest* until then, with
  **Stop sending**.
- **The message**: the email as it was sent, with the subject at its head, and above it its
  type and *Replies go to:* with the Reply-To address its copies carried. Fields such as
  *{first_name}* show as written, because each person's copy had their own details filled
  in. Under it, a line says whether the people it went to can read it again under
  **Messages**, with **Hide from Messages** or **Show in Messages** (`Messages`_).
- **Who received it**: the delivery report, described next.


The delivery report
===================

**Who received it** shows what became of every copy, including what happened after it
left CalDART.

At its top are the counts: **Delivered**, **Failed**, **Skipped**, **Bounced**, and
**Retried**. **Delivered** counts the copies that went and have not come back, so
**Delivered** and **Bounced** together are the people the line above calls *Sent to*. Under
the counts is **Retry failed** (below).

Then one line per person in the batch, with **Name**, **Email**, **Result**, **Reason**,
**Tried at**, **Kind**, **DART**, and **Copy**. **Result** narrows the table to one result,
such as *Failed*, and **Find a person** to a name or address. **Download results** saves
the whole table as a spreadsheet file, with each person's result, reason, and the time
their copy was tried.

Each **Result** reads:

- *Sent*: CalDART handed the copy to the mail server.
- *Failed*: the mail server refused it. The reason reads *Refused by the mail server*, or
  *Temporarily refused, gave up after 3 retries* when the server asked CalDART to wait and
  then kept refusing.
- *Skipped*: the person could not receive it, for the reason given, such as *Address
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

**View copy**, on the line of anybody whose copy was tried, opens that person's copy
exactly as it went, under the table: who it went to and when, its subject, and the email
itself, with the details that were filled in for them at the time, even if they have
changed their profile since. This answers "what did I get?" Its links open in a new tab.
The unsubscribe link at its foot is shown but does nothing here, since it belongs to the
person the copy went to. **Close**, or the Escape key while you are in the copy, shuts it and
returns you to the line you opened it from. Somebody who was skipped, or not sent a copy
yet, has no copy to view.

Retry failed
------------

When the mail server refused some copies, **Retry failed** sends a fresh copy to those
people only, once you press **Retry now**. Nobody already sent a copy gets another, and
nobody whose copy bounced (their address is bad) or who was skipped is sent one. Each person
is checked again first, as for any send: one whose account has since been deleted or
deactivated, whose address has bounced, or who has turned this kind of email off is marked
*Skipped* with the reason, and an address a user administrator has corrected since is the
one the fresh copy goes to. The copies start going within a minute, and the page shows their
progress as for any send. The message reads *The failed copies will be sent again within a
minute.* If everybody whose copy failed is skipped this way, nothing is sent and the page
says *Nobody whose copy failed can be sent one now.*

**Retry failed** cannot be pressed when no copy failed, and says so. On a stopped email it
says to send the rest first: press **Send the rest**, and once that has finished, retry the
failed copies. Each retry is listed under **Retries** at the foot of the report, with when
it was pressed, who pressed it, and how many people it sent a fresh copy to.


Messages
========

Every person a bulk email went to can read it again on their own **Messages** page, and
every copy ends with a *View this email in your browser* link to it there. Each person sees
only their own copy.

To take an email off everybody's Messages, for example a call for volunteers that no longer
applies, press **Hide from Messages** under the message, then **Hide it**. The email reads
*hidden*, and nobody it went to sees it under Messages any more, nor through the link in
their copy. Nothing else changes: this page, its counts, and its results stay as they are.
**Show in Messages** puts it back at once. Only CalDART management sees these buttons.
Each copy also appears in the log of sent emails as *Bulk email*.


If something looks wrong
========================

If somebody says the email never arrived, find their row. *Sent* means CalDART handed the
copy to the mail server, so ask them to check their spam folder, or point them to their
Messages page, where they can read it. *Failed*, *Bounced*, or *Skipped* gives the reason.
After a failure the mail server reported, **Retry failed** may get the copy through. An address that needs correcting is corrected on the person's account by a user
administrator or an account administrator. To write to the people a failure left out, download
the results and add them to a new email.
