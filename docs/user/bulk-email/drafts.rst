:roles: management

==================
Drafts & scheduled
==================

**Drafts & scheduled** lists every bulk email not yet sent: the ones still being written, the
ones in their two minutes before sending, and the scheduled ones. CalDART management opens it
as **Drafts & scheduled** under **Bulk Email** in the menu. A system administrator can open it
too. Every member of CalDART management sees every draft, with who is writing it.


What you see
============

One line per email, the most recently changed first:

- **Subject**: the subject so far, or *(no subject yet)*. It opens the email in
  :doc:`compose`.
- **Status**: a dot and *Draft*, *Scheduled*, or *Waiting to send* for an email in its two
  minutes before sending.
- **When**: *Scheduled for* the date and time, or *Starts in* a countdown.
- **People**: how many are in the batch.
- **From**: who is writing it.
- **Last edited**: when the email or its batch last changed.

**Write a new email** at the top opens :doc:`compose`. Before the first draft the table reads
*No drafts*.


What you can do
===============

- **Open** goes to the email's compose screen, where you can carry on writing, change the
  batch, or send it. A scheduled email can still be changed there until it starts.
- **Cancel schedule** on a scheduled email, or **Cancel** on one waiting to send, turns it
  back into a draft. Nothing in it is lost, and a line confirms *Sending was canceled. The
  email is a draft again.*
- The trashcan on a draft deletes it with its batch, after you press **Delete**. A
  scheduled email must be canceled before it can be deleted.

Once an email starts sending it leaves this list and appears under :doc:`sent`.


If something looks wrong
========================

A draft that has gone missing has either been deleted or has started sending; look under
:doc:`sent`. A scheduled email that shows *Starting now* for more than a few minutes is
waiting for the server's sender, which a system administrator can start by hand from the
Scheduled page.
