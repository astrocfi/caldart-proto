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

Three rules are enforced by the server, not just hidden in the interface:

* **You cannot deactivate your own account.**  The switch is disabled on your
  own record, and the API refuses it even if you go around the interface.
* **Only a system administrator may move the ``system_admin`` role.**  As a user
  administrator you can edit every other role on a system administrator's
  account, but you cannot grant that role to anyone or take it away.
* **You cannot change the email address or the Active box of an account that
  holds a role you do not hold.**  Any role counts, not just the administrative
  ones: a user administrator may move a plain member's address, or another user
  administrator's, but not a DART leader's, a website administrator's, an
  account administrator's or a system administrator's.  Names are not covered:
  you can correct anybody's spelling.

The last of those judges the save in front of it, not the person making it.
Roles are yours to grant, so on every role but ``system_admin`` you can lift the
refusal yourself — tick the missing role on your own account and save.  The
account you genuinely cannot touch is a system administrator's, because the rule
above it keeps ``system_admin`` out of your hands in both directions.


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

An address you may not move is refused for a different reason.  The email
address is where a password reset link goes, so moving somebody's address is
enough to take their account over, and the server allows it only when you
already hold every role that account holds — every role, ``dart_leader`` and
``website_admin`` as much as the administrative ones.  Granting roles is your
job, so for every role but ``system_admin`` the missing role is one you can give
yourself: tick it in the Roles section below, save, and the address is yours to
move.  Take the refusal as a prompt to be sure you are moving the address of the
person you think you are, and to leave a colleague's account to them.  Only
``system_admin`` is beyond you, because only a system administrator may move
that role: a system administrator's account — including one carrying Django
superuser access without the role — stays out of reach until one of them makes
the change.  The same applies to the Active box; names are free to edit either
way.

Roles
-----

The Roles section lists every role with a one-line description of what it
grants, straight from the server, so the list stays right as roles are added.

#. Open **Users & roles** and find the account.
#. Open it, and scroll to **Roles**.
#. Tick the roles they should have; untick the ones they should not.
#. Press **Save changes** — nothing is saved until you do.
#. Tell them to reload the portal, so their menu picks up the change.

Things worth knowing:

* Roles are **additive**.  Leave ``member`` ticked when you add
  ``dart_leader``: taking it away removes their own profile and renewal
  screens.
* ``system_admin`` implies every other role in permission checks, and also makes
  the account a Django superuser.  Grant it sparingly.
* Removing ``system_admin`` takes the superuser flag away again.  An account
  that has the flag but never had the role — the one the site was installed
  with, typically — counts as a system administrator all the same, so only a
  system administrator can change its ticks: leaving the role unticked would
  take that access away, and ticking it is granting the role.  Leave them as
  you found them and the form still saves — a name correction on such an
  account goes through like any other.
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


When something goes wrong
=========================

**"Only a system administrator can grant or revoke the system_admin role."**
   Exactly what it says.  Ask a system administrator.  You will also see it when
   you change any tick on an account that carries Django superuser access
   without the role: saving a changed Roles section rebuilds that access from the
   ticked boxes, so the change would either take the access away or grant the
   role outright.  Put the ticks back as you found them and the save goes
   through; a name correction was never the part it objected to.

**"You cannot deactivate your own account."**
   Deliberate, so the last administrator cannot lock everybody out by
   accident.  Ask a colleague.

**The email address will not save.**
   Another account already uses it, case ignored.  Search for that address:
   you have probably found the duplicate account you were looking for.

**"You cannot change the email address of an account that holds roles you do not hold."**
   The account carries a role you do not have — ``dart_leader``,
   ``website_admin``, ``account_admin`` or ``system_admin`` — and moving an
   address is enough to take an account over, so the server reserves it for
   somebody who already holds every role that account holds.  Ask a system
   administrator, or a colleague who holds them all.  The Active box answers
   "You cannot activate or deactivate an account that holds roles you do not
   hold." for the same reason, and neither refusal changes anything on the
   record.

**Send password reset is grayed out.**
   The account is deactivated.  Tick **Active**, save, then send the link.

**Send password reset says no email was sent.**
   Same cause, if the account was deactivated between opening the page and
   pressing the button.  Reload the record and check the Active box.

**You ticked a role and the person still cannot see the page.**
   They are holding an old session's menu.  Ask them to reload the portal.  If
   it still does not appear, check you pressed **Save changes** — the
   checkboxes do not save themselves.

**You cannot find an account you are sure exists.**
   Search matches first name, last name and email, and ANDs the words you
   type, so a middle name or a typo excludes everybody.  Search for one word,
   or for a fragment of the email address.

**You need to change a member's profile, membership or payments.**
   None of that is on this screen.  It belongs to an account administrator —
   see :doc:`account-administrator-guide`.


See also
========

* :doc:`getting-started` — what members see, including the reset flow from
  their side.
* :doc:`account-administrator-guide` — profiles, memberships and payments.
* :doc:`../developer/api-auth` — the endpoints these screens call, for anyone
  scripting against them.
