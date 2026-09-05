========================
User administrator guide
========================

A **user administrator** looks after accounts: who has one, what they are
allowed to do, and how they get back in when they are locked out.  The role is
deliberately narrow — it does not include editing member profiles, granting
membership terms or taking payments, which belong to the account administrator.

Everything here lives at ``/portal/admin/users``, reachable from
**Administration → Users & roles** once you hold the ``user_admin`` role.  A
``system_admin`` sees the same screens.


What the role covers
====================

=========================================  ================================
You can                                    You cannot
=========================================  ================================
List and search every account              Edit member profiles
Grant and remove roles                     Grant or extend memberships
Deactivate and reactivate accounts         See or refund payments
Correct names and email addresses          Delete an account
Send a password reset link                 Read or set anyone's password
=========================================  ================================

Two rules are enforced by the server, not just hidden in the interface:

* **You cannot deactivate your own account.**  The switch is disabled on your
  own record, and the API refuses it even if you go around the interface.
* **Only a system administrator may move the ``system_admin`` role.**  As a user
  administrator you can edit every other role on a system administrator's
  account, but you cannot grant that role to anyone or take it away.


Finding an account
==================

The list shows every account, 25 to a page, sorted alphabetically by surname
until you sort it otherwise.

**Search**
   Matches first name, last name and email address.  Several words all have to
   match, so ``Ada Lovelace`` finds one person rather than everyone called Ada.
   The search runs as you type.

**Filter by role**
   The row of role buttons above the table narrows the list to holders of one
   role.  Click the pressed button again, or **Any role**, to clear it.

**Account status**
   *Active and deactivated* (the default), *Active only* or *Deactivated only*.

Each row shows the person's roles, their membership status chip, and whether the
account is active.  Click their name to open the record.


Changing what someone may do
============================

Open the account and you get three panels: a read-only summary of where their
membership stands, the editable **Account** form, and **Password**.

Names and email
---------------

Correct a misspelt name, or move an account to a new address, in the Account
form.  The email address is also the login, so tell the person you have changed
it.  Addresses are unique regardless of case: if another account already uses
the address you type, the form says so and saves nothing.

Roles
-----

The Roles section lists every role with a one-line description of what it
grants, straight from the server, so the list stays right as roles are added.
Tick or untick, then **Save changes** — nothing is saved until you do.

Things worth knowing:

* Roles are **additive**.  Leave ``member`` ticked when you add
  ``dart_leader``: taking it away removes their own profile and renewal
  screens.
* ``system_admin`` implies every other role in permission checks, and also makes
  the account a Django superuser.  Grant it sparingly.
* Removing ``system_admin`` takes the superuser flag away again.
* ``website_admin`` is what opens the Wagtail admin at ``/admin/``.  Saving it
  sets the account's Django "staff" flag, and removing it clears the flag
  again — so granting the role is the whole job, and there is nothing else to
  switch on.
* A role change takes effect on the person's next request; if they are signed in
  they may need to reload the portal to see the new menu entries.

Activating and deactivating
---------------------------

Untick **Active** and save.  A deactivated account cannot sign in — the sign-in
page tells them the account has been deactivated — and no password reset email
will be sent to it.  Nothing is deleted: their profile, membership history and
payments stay exactly as they were, and ticking the box again restores access.

Deactivation is the right tool for someone who has left, or an account you
suspect has been compromised.  Deleting members outright is an account
administrator's job, and it is a hard delete — see
:doc:`account-administrator-guide`.


Helping someone back in
=======================

Use **Send password reset** on their record.  This emails them a one-time link
to choose a new password; you never see the password, and neither does anyone
else.  The toast confirms which address it went to — worth reading, because it
is the address on the account, which may not be the one they emailed you from.

The button is disabled for a deactivated account.  Reactivate first, then send
the link.

The link expires after three days and stops working as soon as it is used.  If
they take too long, send another.

If somebody asks you to *tell* them their password, or to set a particular
password for them, you cannot: passwords are stored hashed, and the API has no
endpoint that sets one directly.  The reset link is the whole mechanism.


A few common tasks
==================

**"I have a new DART leader."**
   Search their name, open the record, tick ``dart_leader``, save.  Leave
   ``member`` ticked.

**"Someone has two accounts."**
   Decide which one keeps the membership history — the summary panel at the top
   of each record tells you — and deactivate the other.  Ask an account
   administrator if the records need merging.

**"They changed jobs and lost their email address."**
   Edit the email address on the account, then send a password reset to the new
   one so they can confirm it works.

**"They are locked out and the reset email never arrives."**
   Check the address on the record first: nine times out of ten it is an old
   one.  Correct it, then send the reset again.

**"They can sign in but the page says 403."**
   That is a missing role, not a broken account.  The 403 page names the role
   the page wanted; tick it and save.


See also
========

* :doc:`getting-started` — what members see, including the reset flow from
  their side.
* :doc:`account-administrator-guide` — profiles, memberships and payments.
* :doc:`../developer/api-auth` — the endpoints these screens call, for anyone
  scripting against them.
