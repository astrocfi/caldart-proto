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

- **Subject**: what it said. It opens the email's own page, below.
- **Type**: the kind of email it was, such as *Operational*.
- **Date**: the day it started sending.
- **From**: who sent it.
- **Status**: a dot and *Sending*, *Sent*, *Stopped*, or *Waiting to send the rest*.
- **Sent**, **Failed**, and **Skipped**: how many copies went, were refused by the mail
  server, and were never sent because the person could not receive them.
- **Download results** saves the email's results as a spreadsheet file.
- **Duplicate** starts a new draft from the email, below.

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
  as *Sent to 37 people. 1 failed and 4 were skipped.*, or *Everyone was sent a copy.* A
  stopped email reads *Stopped by* who stopped it, with **Send the rest**, which sends it to
  everybody the stop kept it from once you press **Send them now**. Nobody gets it twice, it
  starts within a minute, and the email reads *Waiting to send the rest* until then, with
  **Stop sending**.
- **The message**: the email as it was sent, with the subject at its head and its type above it. Fields such as
  *{first_name}* show as written, because each person's copy had their own details filled
  in.
- **Who received it**: one line per person in the batch, with **Name**, **Email**,
  **Result**, **Reason**, **Tried at**, **Kind**, and **DART**. **Find a person** narrows it
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


Duplicate
=========

**Duplicate**, on each line of the list and on the email's own page under **Where it stands**,
starts a new draft of your own from the email. It asks how:

- **Copy the message**: the new draft has the email's subject, message (pictures included),
  and type, and an empty batch.
- **Copy the message and the people**: the batch holds everybody the email was for too, as
  their accounts are now. Whether each receives the new email is worked out afresh, so
  somebody who has since turned that kind of email off, or whose address bounced, shows as
  skipped. The batch's **Chosen by** reads *Copied from* and the subject. Accounts deleted
  since are left out.

The new draft opens on :doc:`compose`, ready to change and send. The email you copied stays as
it was. **Cancel** closes the question without copying anything.


If something looks wrong
========================

If somebody says the email never arrived, find their row. *Sent* means CalDART handed the
copy to the mail server, so ask them to check their spam folder. *Failed* or *Skipped* gives
the reason. An address that needs correcting is corrected on the person's account by a user
administrator or an account administrator. To write to everybody again, use **Duplicate**
with the people; to write to only the people a failure left out, download the results and add
them to a new email.
