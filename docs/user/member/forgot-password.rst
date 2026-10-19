:signed-out: yes

====================
Forgot your password
====================

The **Forgot your password?** screen emails you a link to set a new password when you
can't remember yours. Open it from the link under the **Sign in** button (see
:doc:`sign-in`).


What you see
============

One box, **Email address**, and the **Email me a link** button. **Back to sign in**
returns you to the sign-in screen.


What you do
===========

#. Type the email address your account uses.
#. Press **Email me a link**.
#. The screen changes to **Check your email**: *If an account uses
   marta.reyes@example.org, a reset link is on its way. The link works once and
   expires in 3 days.*
#. Open the email and follow its link. It opens :doc:`reset-password`, where you
   choose the new password.

The screen says the same thing whether or not it knows the address. That is on
purpose, so a stranger can't use the form to find out who has an account.


The email
=========

The message arrives with the subject *CalDART: reset your password*. It has one
link in it. Two things to know about the link:

* **It works once.** Following it a second time, or after you have already set a
  new password, shows *That password reset link is invalid or has expired. Request
  a new one.*
* **It expires after three days.** If it has expired, ask for a fresh one.

The link also proves that the address is yours. If you hadn't verified your address
yet, it counts as verified once you set the new password.

CalDART sends the link to a deactivated account too, and setting the new password
reactivates the account. If an administrator has closed the account, CalDART doesn't
send the email, but the screen says the same thing.


Nothing arrived?
================

The most likely reasons come first:

#. It went to your spam or junk folder.
#. You typed a different address from the one on your account. The **Check your
   email** screen offers *try another address*: follow it and try the other
   addresses you use.
#. You don't have an account yet. You want :doc:`join`.

*Too many tries. Try again in ... seconds.* means too many reset
requests have come from your network in the last hour. Wait the time it gives and
try again.


If something looks wrong
========================

A user administrator can send you a reset link from your user record. That is the
quickest way through when you aren't sure which address your account uses. Ask the
office, using the contact address at the bottom of every public page.
