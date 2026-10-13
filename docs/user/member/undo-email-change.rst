:signed-out: yes

=============
Change undone
=============

The **Change undone** screen is where the link in a change-of-address notice takes
you. CalDART sends that notice to the address your account had whenever somebody asks
to move the account to another address, and again when the move is made (see
:doc:`change-email`). If the change was yours, you need do nothing. If it was not,
the link takes your account back.


When CalDART sends the notice
=============================

Two messages go to your address, each with the link:

* *CalDART: your email address is changing*, when somebody asks for the change. The
  account keeps signing in with your address until somebody opens the link sent to
  the new one.
* *CalDART: your email address has changed*, when that happens.

They go only to an address you have verified (see :doc:`verify-email`). The link in
either works once, for seven days. In the message it is the button **This was not
me** or **Put my address back**.

For those seven days after a change, your previous address stays reserved for you:
nobody else can open an account with it or move to it, your account's address cannot
change again from **Change email**, and only a link sent to your previous address can
undo anything. If an account administrator changes the address meanwhile, the notices
come to your previous address too.


What you see
============

The screen asks **Undo the change of address?** and says what undoing does. Nothing
happens until you press **Undo the change**, so opening the link, or a mail program
checking it, changes nothing. The screen then says **Change undone**: *Your sign-in
address is marta.reyes@example.org. Everybody has been signed out of the account, and
its password no longer works. We sent marta.reyes@example.org a link to choose a new
one.*

Pressing the button does all of this at once:

* if the account had already moved, your address is put back, and it is the address
  you sign in with again;
* a change still waiting is dropped, so the link sent to the other address no longer
  works;
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
  has been followed already. Following one link spends every link sent before it,
  so an earlier notice's link does nothing once you have used a later one.

Under the reason, **Forgot your password?** opens :doc:`forgot-password`.

If the screen says **Account secured** instead, another account already held your
previous address, so it could not be put back. Everything else was done: everybody is
signed out, the password no longer works, and the link to choose a new one went to
your previous address. The account still signs in with the address it was moved to.
Write to the office, using the contact address at the bottom of every public page,
and they will help you move it back.


If something looks wrong
========================

If the reset message does not arrive, look in your spam folder, then ask for another
from :doc:`forgot-password` with your address. If you cannot get back in, write to
the office, using the contact address at the bottom of every public page.
