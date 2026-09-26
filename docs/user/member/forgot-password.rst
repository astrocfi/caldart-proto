====================
Forgot your password
====================

The **Forgot your password?** screen sends you a link to set a new password when you
cannot remember the one you have. Open it from the link under the **Sign in** button
(see :doc:`sign-in`).


What you see
============

One box, **Email address**, and the **Email me a link** button. **Back to sign in**
returns you to the sign-in screen.


What you do
===========

#. Type the email address your account uses.
#. Press **Email me a link**.
#. The screen changes to **Check your email**: *If an account uses
   marta.reyes@example.org, a reset link is on its way. The link can be used once
   and expires in a few days.*
#. Open the email and follow its link. It opens :doc:`reset-password`, where you
   choose the new password.

The screen answers the same way whether or not it knows the address. That is on
purpose: the form must not tell a stranger who has an account.


The email
=========

The message arrives with the subject *CalDART: reset your password*. It holds one
link. Two things to know about it:

* **It works once.** Following it a second time, or after you have already set a
  new password, shows *That password reset link is invalid or has expired. Request
  a new one.*
* **It expires after three days.** Ask for a fresh one if it has.

Following the link also confirms that the address is yours, so an unverified
address becomes verified when you set the new password.

A deactivated account gets no email from this screen. A user administrator who
tries to send one is told so.


Nothing arrived?
================

In order of likelihood:

#. It went to your spam or junk folder.
#. You typed a different address from the one on your account. The **Check your
   email** screen offers *try another address*: follow it and try the other
   addresses you use.
#. You have no account yet. You want :doc:`join`.

*Request was throttled. Expected available in ... seconds.* means too many reset
requests have come from your network in the last hour. Wait the time it gives and
try again.


If something looks wrong
========================

A user administrator can send you a reset link from your user record, which is the
quickest way through when you are not sure which address your account uses. Ask
the office, using the contact address at the foot of every public page.
