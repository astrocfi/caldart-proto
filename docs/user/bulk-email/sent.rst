:roles: management

====
Sent
====

**Sent** lists every bulk email that has gone out, or is going out now, and what became of
each copy. CalDART management opens it as **Sent** under **Bulk Email** in the menu. A system
administrator can open it too.


The list
========

One line per email, the most recently started first:

- **Date**: when it started sending.
- **Subject**: what it said. It opens the email's own page, below.
- **From**: who sent it.
- **Status**: a dot and *Sending*, *Sent*, or *Stopped*.
- **Sent**, **Failed**, and **Skipped**: how many copies went, were refused by the mail
  server, and were never sent because the person could not receive them.
- **CSV** downloads the email's results as a spreadsheet file.

Before the first send the table reads *No bulk email has been sent*. The list keeps itself up
to date while an email is sending.

**Stop** on an email that is sending stops it after the copy going out now, once you press
**Stop now**. Copies already sent cannot be called back. **Send the rest** on a stopped email
sends it to everybody the stop kept it from, once you press **Send them now**. Nobody gets
it twice, and it starts within a minute.


One email's page
================

The page of one sent email has three cards:

- **Where it stands**: while it sends, *Sending… 12 of 38 sent, about 1 minute left.* with a
  bar and **Stop sending**. When it is finished, a line such as *Sent to 37 people. 1 failed
  and 4 were skipped.* A stopped email reads *Stopped by* who stopped it, with **Send the
  rest**.
- **The message**: the subject and the message as they were sent.
- **Who received it**: one line per person in the batch, with **Name**, **Email**,
  **Kind**, **DART**, **Result**, **Reason**, and **Tried at**. **Find a person** narrows it
  to a name or address, and **Download results** saves it as a spreadsheet file with each
  person's result and reason.

Each **Result** reads:

- *Sent*: CalDART handed the copy to the mail server.
- *Failed*: the mail server refused it. The reason reads *Refused by the mail server*, or
  *Temporarily refused, gave up after 3 retries* when the server asked CalDART to wait and
  then kept refusing.
- *Skipped*: the person could not receive it, for the reason given, such as *Address
  bounced*. The reasons are listed on :doc:`compose`.
- *Not sent (stopped)*: the email was stopped before this copy went. The reason names who
  stopped it.
- *Not sent yet*: the copy is waiting its turn while the email sends.

Each copy also appears in the log of sent emails as *Bulk email*.


If something looks wrong
========================

If somebody says the email never arrived, find their row. *Sent* means CalDART handed the
copy to the mail server, so ask them to check their spam folder. *Failed* or *Skipped* gives
the reason. An address that needs correcting is corrected on the person's account by a user
administrator or an account administrator. To write to the people a failure left out, download
the results and add them to a new email.
