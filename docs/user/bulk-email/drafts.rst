:roles: management, dart_leader

====================
Drafts and scheduled
====================

**Drafts and scheduled** lists every bulk email that hasn't been sent yet: the ones still being
written, the ones in their two-minute wait before sending, and the scheduled ones. CalDART
management finds it under **Bulk email** in the menu. A system administrator can open it too.
Every member of CalDART management sees every draft, whoever wrote it. A DART leader opens it
too, and sees only their own (:doc:`dart-leaders`).


What you see
============

There is one line per email, with the most recently changed first:

- **Subject**: the subject so far, or *(no subject yet)*. A field in it shows as a chip, as on
  :doc:`compose`. Press the subject to open the email in :doc:`compose`.
- **Type**: the type of email, or a dash until you choose one.
- **From** and **DART**, for CalDART management only: who is writing it, and the DART a DART
  leader's email goes to, or a dash for an email that may go to anybody.
- **Status**: a dot and *Draft*, *Scheduled*, or *Waiting to send* (an email in its two-minute
  wait).
- **When**: the date and time a scheduled email goes out, such as *10/04/2026 at 8:00 AM*, or
  *Starts in* and a countdown. Like every time in the portal, it is in Pacific time.
- **People**: how many people are on the recipient list.
- **Last edited**: the day the email or its recipient list last changed.
- **Actions**, last: **Cancel schedule** or **Cancel** on an email waiting to send, and the
  trashcan on a draft (below).

On a narrow screen, columns drop out one at a time until the rest fit: first **Type**, then
**DART**, **Last edited**, and **From**. That keeps the actions in sight. On a phone, the table
scrolls sideways, a note above it says so, and the subject stays pinned at the left. **New
email** at the top opens :doc:`compose`. Until there is a draft, the table says *No drafts* and
has its own **New email** button. If a DART leader's profile doesn't name a DART, they see a
line telling them to set their DART on My profile, with **Open "My profile"**, instead of **New
email** (:doc:`dart-leaders`).

If an email came due but wasn't sent, a line above the table names it and gives the reason,
such as *This email wasn't sent, because you can't send Mission email anymore. Choose
another type and send again.* This happens when the person who pressed **Send** has since lost the role
that sends that type of email, or their account was deleted. The email is a draft again, and
nothing is lost. Open it, choose a type you may send, and send it again. The same line shows
at the top of its compose screen until you do.


What you can do
===============

- Press the subject to carry on writing, change the recipient list, or send it. You can still
  change a scheduled email there until it starts. If you change who gets it, or its type, it
  goes back to being a draft, since the number of people may change. A line says *The type
  changed, so this email is back in your drafts. Press Send or Schedule again when it is
  ready.*, or the same about the recipients. Changing the words leaves the schedule as it is.
- **Cancel schedule** on a scheduled email, or **Cancel** on one waiting to send, turns it
  back into a draft. Nothing in it is lost, and a line confirms *Sending was canceled. The
  email is a draft again.*
- The trashcan on a draft deletes it with its recipient list, after you press **Delete**. You
  must cancel a scheduled email before you can delete it.

Once an email starts sending, it leaves this list and moves to :doc:`sent`. It stays there,
even after **Send the rest**.


If something looks wrong
========================

If a draft has gone missing, it was either deleted or has started sending. Look under
:doc:`sent`. If an email still says *Starting now* a few minutes after its two minutes ended,
it is waiting for the sender on the server. A system administrator can start the sender by
hand from the Scheduled tasks page.
