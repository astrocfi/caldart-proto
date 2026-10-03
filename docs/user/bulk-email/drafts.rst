:roles: management

==================
Drafts & scheduled
==================

**Drafts & scheduled** lists every bulk email not yet sent: the ones still being written, the
ones in their two minutes before sending, and the scheduled ones. CalDART management opens it
as **Drafts & scheduled** under **Bulk Email** in the menu. A system administrator can open it
too. Every member of CalDART management sees every draft.


What you see
============

One line per email, the most recently changed first:

- **Subject**: the subject so far, or *(no subject yet)*. Press it to open the email in
  :doc:`compose`.
- **Type**: the kind of email chosen, or a dash before one is.
- **Status**: a dot and *Draft*, *Scheduled*, or *Waiting to send* for an email in its two
  minutes before sending.
- **When (Pacific time)**: the date and time a scheduled email goes out, such as *10/04/2026
  at 8:00 AM*, or *Starts in* a countdown.
- **People**: how many are in the batch.
- **Last edited**: the day the email or its batch last changed.

**Write a new email** at the top opens :doc:`compose`. Before the first draft the table reads
*No drafts*. On a narrow screen the table scrolls sideways.

An email that came due but was not sent is named above the table with the reason, such as
*This email was not sent: you can no longer send Mission email. Choose another type and send
again.* This happens when the person who pressed **Send** has since lost the role that sends
that kind of email, or their account was deleted. The email is a draft again with nothing
lost; open it, choose a type you may send, and send it again. The same line shows at the top
of its compose screen until you do.


What you can do
===============

- Press the subject to carry on writing, change the batch, or send it. A scheduled email can
  still be changed there until it starts.
- **Cancel schedule** on a scheduled email, or **Cancel** on one waiting to send, turns it
  back into a draft. Nothing in it is lost, and a line confirms *Sending was canceled. The
  email is a draft again.*
- The trashcan on a draft deletes it with its batch, after you press **Delete**. A
  scheduled email must be canceled before it can be deleted.

Once an email starts sending it leaves this list and appears under :doc:`sent`, and it stays
there, even after **Send the rest**.


If something looks wrong
========================

A draft that has gone missing has either been deleted or has started sending; look under
:doc:`sent`. An email waiting to send that still reads *Starting now* a few minutes after its
two minutes ended is waiting for the server's sender, which a system administrator can start
by hand from the Scheduled page.
