:roles: user_admin

============================
Passwords on the user record
============================

The **Password** card of the :doc:`user-record` sends a person a link to choose a new
password, or shuts an old password out at once. Nobody can read or set a password here.


.. _user-record-new-password:

Requiring a new password
========================

Press **Require a new password** when you think somebody other than the owner knows an
account's password, say because they were tricked into typing it on a fake page. The link goes
to the address at the top of the page, which somebody who took the account over may have
changed, so check first that it is the owner's; if it is not, ask an account administrator to
correct it on the :doc:`member-record`. It asks first and names that address; **Yes, require a
new password** goes ahead. Then the old password stops working at once, for signing in and for
reactivating, and so does any reset link sent earlier; every browser signed in to the account
is signed out; the address is emailed a fresh link with the subject *CalDART: choose a new
password*; and the **History** card records it under your name. The message at the top of the
screen reads *The old password no longer works and every session is ended. A password reset
email went to* and the address. Roles, membership, and status stay as they were.

A deactivated account stays deactivated until its owner chooses a password from the link,
which reactivates it as any reset does. A blocked account isn't sent the email, since the block
refuses the link; once you allow reactivation, the owner uses **Forgot password** on the
sign-in page. If the owner's mailbox itself was taken over, a new password does not help:
block reactivation and reach the owner another way.


Helping someone back in
=======================

**Send password reset** emails the person a one-time link to choose a new password. The
subject reads *CalDART: reset your password*. You never see the password, and neither does
anyone else. The message at the top of the screen reads *Password reset email sent to* and
the address on the account, which may differ from the one they wrote to you from.

The button is disabled on a deactivated account, whose card reads *Reactivate the account
before sending a reset link.* The link stops working after three days, or once used; send
another if they take too long. Nobody can read or set a password here.


If something looks wrong
========================

The sentences the **Password** card can answer with, and what each means, are under *If
something looks wrong* on the :doc:`user-record`.
