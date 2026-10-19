:signed-out: yes

==============
Email verified
==============

The **Email verified** screen is where the link in a verification message takes
you. Following the link proves that the email address is yours.


When CalDART sends a verification message
=========================================

CalDART sends one in two cases:

* when you create an account in :doc:`join`;
* when you reactivate your account and its address was never verified (see
  :doc:`sign-in`).

The message has the subject *CalDART: verify your email address*. Its link works
for three days.

When you move your account to another address on :doc:`change-email`, the new
address gets *CalDART: confirm your new email address* instead. Its link opens this
screen too. Following that link is the step that moves your account.


What you see
============

At first the screen shows **Verifying your email address** and *Checking the link…*
while it checks the link. Then it says **Email verified**, with the address, and a
**Continue** button. The link works in any browser, signed in or not, so it doesn't
matter which device you open the email on.

If the link moved your account, the screen says **Email address changed** instead,
with *marta@example.net is your sign-in address from now on.* Sign in with that
address from then on.

**Continue** takes you to the right place:

* the next step of the join wizard, if you are signed in and haven't finished
  joining (see :doc:`join`);
* your :doc:`dashboard`, if you are signed in and have finished joining;
* the **Sign in** screen with your address already filled in, if you aren't signed
  in. Once you sign in there, you go on into the join wizard.


If the link does not work
=========================

The screen says **Email not verified** with the reason, usually *That verification
link is invalid or has expired.* Sign in, and press **Resend verification
message** on the screen you land on to get a new one. A link sent to a new address
also stops working if you then ask for a different address, or if the change is
undone. If the screen says *Another account already uses that email address.*,
somebody else took the address after you asked for it, and your account keeps the
address it had.

Until you verify your address, that **Check your email** screen is the only part of
the portal you can use. Every other screen brings you back to it, and there isn't a
menu down the left. Changing your address doesn't keep you there. You go on signing
in with the address you had until you confirm the new one (see :doc:`change-email`).


If something looks wrong
========================

If no message arrives, look in your spam or junk folder first, then press **Resend
verification message**. If the address itself is wrong, correct it on
:doc:`change-email`, and a fresh message goes to the corrected address. You can
resend only a few times an hour. After that the screen says *Too many tries. Try
again in ... seconds.* Wait that long and try again.
