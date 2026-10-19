============
Change email
============

The **Change email** screen moves your account to another address. Open it from
**Change email** under **My account** in the menu. It starts by naming the address you
sign in with: *Your sign-in address is marta.reyes@example.org. We will send a link to
the new address; the change takes effect when you open it.*

You sign in with your address, and password reset links go to it. So nothing
changes until you prove that the new address is yours.


What you see
============

Two boxes:

**New email address**
  The address you want to sign in with.

**Current password**
  Your password, to prove the request is yours.

Press **Change email**. To leave without changing anything, choose another screen in the
menu.


What happens next
=================

*We sent a link to marta@example.net. Your sign-in address stays
marta.reyes@example.org until you follow it.* appears. You stay signed in, and you
can still use the whole portal.

CalDART sends two emails:

* The new address gets *CalDART: confirm your new email address*. Open its link, and
  the screen says **Email address changed** and *marta@example.net is your sign-in
  address from now on.* (see :doc:`verify-email`). The link works for three days.
* Your current address gets *CalDART: your email address is changing*, so that you
  hear about any change you didn't ask for. When the change happens, it also gets
  *CalDART: your email address has changed*. Each email has a link that undoes the
  change (see :doc:`undo-email-change`). If the change is yours, ignore them. If you
  never verified your current address, CalDART doesn't send these.

Until you open the link, you sign in with your current address. This screen shows a
**Change waiting** card with the same sentence and a **Resend verification message**
button, which sends the link to the new address again. To move to a different
address instead, change it again. Only the most recent link works.

Capital letters don't make a difference: Marta@example.org and marta@example.org are the
same address.

You can also fix a mistyped address from the **Check your email** step of the join
wizard. The step then shows the waiting address and sends the link there. Open the
link, and the wizard goes on.


If the screen says something else
=================================

*That is not your current password.*
  The password is wrong. Type it again.

*That is already your email address.*
  The new address is the same as your current one.

*Your sign-in address changed in the last seven days, so it cannot change again until 10/19/2026.*
  For seven days after a change, CalDART holds your previous address so that you can
  undo the change from it (see :doc:`undo-email-change`). During that time your
  address can't change again. Wait until the date it gives. An account administrator
  can still change it for you.

*Too many tries. Try again in ... seconds.*
  Too many change requests have come from your network in the last hour. Wait the
  time it gives.


If something looks wrong
========================

If the message to the new address doesn't arrive, look in your spam folder, then
press **Resend verification message** in the **Change waiting** card. If you typed the
new address wrong, change it again to the right one. If a message never arrives, the
address may already belong to another account. Each address belongs to one account,
so CalDART never sends a link to an address another account uses. Choose another
address, or sign in to the other account if it is yours. If the link says *Another
account already uses that email address.*, somebody else took the address after you
asked for it. Choose another.

Changing your password cancels a change that is still waiting, and its link stops
working. Ask again if you still want the change.

An account administrator can also change your address on your member record. That
works the same way. The new address gets the link, and your current address gets
the notices.
