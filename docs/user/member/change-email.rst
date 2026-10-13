============
Change email
============

The **Change email** screen moves your account to another address. Open it from
**Change email** under **My account** in the menu. It starts by naming the address you
sign in with: *Your sign-in address is marta.reyes@example.org. We will send a link to
the new address; the change takes effect when you open it.*

Your address is how you sign in and where a password reset link goes, so nothing
changes until the new address has proved it is yours.


What you see
============

Two boxes:

**New email address**
  The address you want to sign in with from now on.

**Current password**
  Your password, to prove the request is yours.

Press **Change email**. To leave without changing anything, choose another screen in the
menu.


What happens next
=================

*We sent a link to marta@example.net. Your sign-in address stays
marta.reyes@example.org until you follow it.* appears. You stay signed in, and the
whole portal stays open to you.

Two messages go out:

* The new address gets *CalDART: confirm your new email address*. Open its link: the
  screen says **Email address changed** and *marta@example.net is your sign-in
  address from now on.* (see :doc:`verify-email`). The link is good for three days.
* Your current address gets *CalDART: your email address is changing*, so that you
  hear of a change you did not ask for. When the change is made, it gets *CalDART:
  your email address has changed* as well. Each has a link that undoes the change
  (see :doc:`undo-email-change`). If the change is yours, ignore them. An address you
  never verified is not sent these.

Until you open the link, you sign in with your current address, and this screen
shows a **Change waiting** card with the same sentence and a **Resend verification
message** button, which sends the link to the new address again. To move to a
different address instead, change it again: only the newest link works.

Capital letters make no difference: Marta@example.org and marta@example.org are the
same address.

If you change the address from the join wizard's **Check your email** step, to fix a
mistyped address, the step names the address waiting and sends its link there. Open
it and the wizard carries on.


If the screen says something else
=================================

*That is not your current password.*
  The password is wrong. Type it again.

*That is already your email address.*
  The new address is the one you have.

*Your sign-in address changed in the last seven days, so it cannot change again until 10/19/2026.*
  For seven days after a change, the address you left is kept so that you can undo the
  change from it (see :doc:`undo-email-change`), and your address cannot change again.
  Wait until the date it gives. An account administrator can still change it for you.

*Request was throttled. Expected available in ... seconds.*
  Too many changes have been asked for from your network in the last hour. Wait the
  time it gives.


If something looks wrong
========================

If the message to the new address does not arrive, look in your spam folder, then
press **Resend verification message** in the **Change waiting** card. If you typed the
new address wrong, change it again to the right one. If no message ever arrives, the
address may already belong to another account, which is never sent a link: each
address belongs to one account, so choose another, or sign in to the other account if
it is yours. If the link says *Another account already uses that email address.*,
somebody took the address after you asked for it; choose another.

Changing your password drops a change still waiting, and its link stops working; ask
again if you still want it.

An account administrator can also change your address on your member record. That
works the same way: the new address is sent the link, and your address is told.
