===========
User record
===========

The **user record** is one account seen by a user administrator: where its membership
stands, its name and address, whether it can sign in, the roles it holds, and a button that
sends a password reset link. Open it by clicking a name on :doc:`users`.


What you see
============

The person's name heads the page, with their address under it and **Back to users** beside
it. Three cards follow.

**Where this account stands**
   The kind of account (**Member**, **Friend**, or **Donor**), the membership chip, and
   *Profile complete* or *Profile incomplete*. A donor's card adds *A donor gave through the
   public site and cannot sign in. Fix the email address here if a receipt went astray.*

**Account**
   **First name**, **Last name**, and **Email address**, with the hint *This is also how
   they sign in.* and **Verified** with a date, or **Unverified**. Then **Account status**
   (*Active — the account can sign in*) and **Roles**, a box for each role with a line
   saying what it grants.

**Password**
   **Send password reset**, which a donor's record leaves out.

Nothing is saved until you press **Save changes**, and the message *Account saved.* confirms
it. **Reset form** puts every box back the way the account has it.


Changing a name or an address
=============================

Correct a misspelled name, or move an account to a new address, in the **Account** card.
The address is also the sign-in, so tell the person you have changed it. Each address
belongs to one account, capitals ignored: if another account already uses the one you type,
the form says so and saves nothing.

A changed address is marked **Unverified**, and CalDART emails the new address a message
with the subject *CalDART: verify your email address*, with your organization's name in
place of CalDART. It counts as verified again once they open the link. A change of capitals
alone is not a new address. People can also change their own address from **Change email**
in the portal's menu.

On an unverified address a **Resend verification message** button sends a fresh link, and
the message at the top of the screen names the address it went to. It is disabled on a
deactivated account. Clicking the link a second time does no harm, so send another whenever
somebody says the first never came.


Granting and removing roles
===========================

#. Find the account on :doc:`users` and open it.
#. Under **Roles**, tick the roles they should have and untick the ones they should not.
#. Press **Save changes**.
#. Ask them to reload the portal, so their menu shows the change.

Things worth knowing:

- Roles add up. **Member** opens no screen of its own, because every signed-in account has
  the member screens.
- **Treasurer** opens the payment screens and nothing that shows a member's medical or
  certificate, so a volunteer who keeps the books needs no access to anybody's medical
  details.
- **Website administrator** opens the website's editor. Granting the role is the whole job;
  there is nothing else to switch on, and removing it closes the editor again.
- **System administrator** can do everything, including the server's own administration
  site. Grant it sparingly. Only a system administrator can grant or remove it.
- A role change takes effect on the person's next visit to a page.


Rules the site enforces
=======================

- **You cannot deactivate your own account.** The box is disabled on your own record, with
  *You cannot deactivate your own account.* under it.
- **Only a system administrator may grant or remove System administrator.** You can change
  every other role on a system administrator's account.
- **The email address and the Active box are guarded.** You can change them only on an
  account whose roles you hold yourself, since moving somebody's address is enough to take
  their account over. As a user administrator you can move an ordinary member's address, or
  another user administrator's, and nobody else's with a role you lack. Because granting
  roles is your job, you can lift this for any role except System administrator: tick the
  missing role on your own record, save, and make the change. Names are never guarded.

Some accounts, typically the one the site was installed with, hold full system access
without the System administrator role ticked. They count as a system administrator here, so
only a system administrator can change their roles. Leave their ticks as you found them and
the rest of the form still saves.


Deactivating and reactivating
=============================

Untick **Active** and save. The account's password no longer signs it in, and nothing is
deleted: the profile, the membership history, and the payments stay as they were. Tick the
box again to restore access.

The person can come back on their own. Signing in with the right password tells them *This
account is deactivated. You can reactivate it.* and offers **Reactivate my account**, and
completing a password reset they asked for reactivates it too. People can also deactivate
their own account from their profile, which cancels their automatic renewal and recurring
donations and sets their membership aside until they return. Unticking **Active** yourself
does neither. Ticking it again on an account the person deactivated themselves brings their
membership back as their own reactivation would.

Deactivation is the right step for someone who has left. It does not keep out somebody who
knows the password, so for an account you think has been taken over, deactivate it and ask
the owner to reset the password once they are back in. Deleting an account is an account
administrator's job, on the **Danger zone** tab of the :doc:`member-record`.


Helping someone back in
=======================

**Send password reset** emails the person a one-time link to choose a new password. The
subject reads *CalDART: reset your password*. You never see the password, and neither does
anyone else. The message at the top of the screen reads *Password reset email sent to* and
the address on the account, which may differ from the one they wrote to you from.

The button is disabled on a deactivated account, whose card reads *Reactivate the account
before sending a reset link.* The link stops working after three days, or as soon as it is
used; send another if they take too long. Nobody can read an existing password, and this
screen cannot set one. The reset link is the way back in.


If something looks wrong
========================

A message that only a system administrator can grant or revoke that role means you changed a
box on a system administrator's account, or on an account with full system access; put the
ticks back and save, or ask a system administrator. *You cannot change the email address of
an account that holds roles you do not hold.* and *You cannot activate or deactivate an
account that holds roles you do not hold.* mean the account holds a role you lack; tick it
on your own record, save, and try again. If the address will not save, another account
already uses it, and you have probably found a duplicate. *That account is deactivated, so
no reset email was sent.* means the account was deactivated while the page was open; reload
and tick **Active** first. If somebody still cannot see a page after you ticked its role, ask
them to reload the portal, and check that you pressed **Save changes**. Profiles,
memberships, and payments are not on this screen; they belong to an account administrator.
