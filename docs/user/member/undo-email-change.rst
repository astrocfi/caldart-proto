:signed-out: yes

=============
Change undone
=============

The **Change undone** screen is where the link in a change-of-address notice takes
you. When somebody asks to move your account to another address, CalDART sends a
notice to the address you had. It sends another when the move happens (see
:doc:`change-email`). If the change was yours, you don't need to do anything. If it
wasn't, the link takes your account back.


When CalDART sends the notice
=============================

Two messages come to your address, each with the link:

* *CalDART: your email address is changing*, when somebody asks for the change. The
  account still signs in with your address until somebody opens the link sent to
  the new one.
* *CalDART: your email address has changed*, when that happens.

CalDART only sends them to an address you have verified (see :doc:`verify-email`).
The link in each works once, for seven days. In the email it is a button: **This was
not me** or **Put my address back**.

For seven days after a change, CalDART holds your previous address for you. Nobody
else can open an account with it or move an account to it. You can't change your
account's address again from **Change email**. Only a link sent to your previous
address can undo anything. If an account administrator changes the address during
those seven days, the notices come to your previous address too.


What you see
============

The screen asks **Undo the change of address?** and says what undoing does. Nothing
happens until you press **Undo the change**. Opening the link doesn't change
anything, and neither does a mail program that checks the link. Once you press the
button, the screen says **Change undone**: *Your sign-in
address is marta.reyes@example.org. Everybody has been signed out of the account, and
its password no longer works. We sent marta.reyes@example.org a link to choose a new
one.*

Pressing the button does all of this at once:

* if the account had already moved, CalDART puts your address back, and you sign in
  with it again;
* a change still waiting is canceled, so the link sent to the other address stops
  working;
* everybody signed in to the account is signed out, on every device;
* the password stops working, since whoever asked for the change may know it;
* a message with the subject *CalDART: reset your password* goes to your address.

Press **Go to sign in**, then open the reset message and choose a new password on
:doc:`reset-password`. Sign in with it from then on (see :doc:`sign-in`).


If the screen says something else
=================================

The screen says **Change not undone**, with the reason:

*That link is invalid, has expired, or has been used.*
  The link is more than seven days old, it was cut short when it was copied, or it
  was already used. Using one link also uses up every link sent before it. So once
  you use a later notice's link, an earlier one doesn't do anything.

Under the reason, **Forgot your password?** opens :doc:`forgot-password`.

If the screen says **Account closed** instead, another account already had your
previous address, so CalDART couldn't put it back. To keep your account away from
whoever moved it, CalDART closed it. Everybody is signed out and its password stops
working. Nobody can sign in, reset its password, or reactivate it. To get it back,
write to the office, using the contact address at the bottom of every public page.


If something looks wrong
========================

If the reset message doesn't arrive, look in your spam folder, then ask for another
from :doc:`forgot-password` with your address. If you can't get back in, write to
the office, using the contact address at the bottom of every public page.
