:roles: user_admin

============================
Passwords on the user record
============================

The **Password** card of the :doc:`user-record` sends a person a link to choose a new
password, or shuts out an old password at once. Nobody can see or set a password here.


.. _user-record-new-password:

Requiring a new password
========================

Press **Require a new password** when you think somebody other than the owner knows an
account's password, for example because the owner was tricked into typing it on a fake
page. The link goes to the address at the top of the page. Somebody who took over the
account may have changed it, so first make sure it is the owner's. If it isn't, ask an
account administrator to correct it on the :doc:`member-record`. The button asks first and
names that address, and **Yes, require a new password** goes ahead.

Then several things happen. The old password stops working at once, for signing in and for
reactivating, and so does any reset link sent earlier. Every browser signed in to the
account is signed out. The address gets an email with a fresh link and the subject
*CalDART: choose a new password*. The **History** card records the change under your name.
The message at the top of the screen says *The old password no longer works and every
session is ended. A password reset email went to* and the address. Roles, membership, and
status stay as they were.

A deactivated account stays deactivated until its owner chooses a password from the link.
That reactivates it, as any reset does. A blocked account doesn't get the email, since the
block refuses the link. Once you allow reactivation, the owner can use **Forgot password**
on the sign-in page. If someone has taken over the owner's mailbox itself, a new password
doesn't help. Block reactivation and reach the owner another way.


Helping someone back in
=======================

**Send password reset** emails the person a one-time link to choose a new password. The
subject is *CalDART: reset your password*. You never see the password, and neither does
anyone else. The message at the top of the screen says *Password reset email sent to* and
the address on the account. That may be different from the address they wrote to you from.

On a deactivated account, the button is disabled, and the card says *Reactivate the account
before sending a reset link.* The link stops working after three days, or once it is used.
If they take too long, send another. Nobody can see or set a password here.


If something looks wrong
========================

The messages the **Password** card can show, and what each one means, are under *If
something looks wrong* on the :doc:`user-record`.
