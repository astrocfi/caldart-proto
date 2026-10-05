:roles: user_admin

===========
User record
===========

The **user record** is one account seen by a user administrator: where its membership
stands, its name and address, the roles it holds, whether it can sign in, and a button that
sends a password reset link. Open it by clicking a name on :doc:`users`.


What you see
============

The person's name heads the page, with their address under it and **Back to users** beside
it. Five cards follow.

**Membership**
   The kind of account (**Member**, **Friend**, or **Donor**), the membership status, and
   *Profile complete* or *Profile incomplete*. A member with no term in force reads *No
   membership yet* (or *No membership in force*), *Membership starts* and the date when
   their term has not begun, or *Membership set aside while deactivated*, as on the
   :doc:`member-record`. A donor's card adds *A donor gave through the
   public site and cannot sign in. Fix the email address here if a receipt went astray.* If
   you are an account administrator too, **Member record** opens the person's
   :doc:`member-record`, where a donor can be deleted.

**Account**
   **First name**, **Last name**, and **Email address**, all three required, with the
   hint *This is also how they sign in.* and **Verified** with a date, or **Unverified**, and **Bounced**, beside
   a red dot, when the address bounces. Then **Roles**, a box for each role with a line saying what it
   grants. Unless you are a system administrator, the **System administrator** box is grayed
   out, and its line adds *Only a system administrator can give or take away this role.*

**Account status**
   Whether the account can sign in, and the actions that change it: **Deactivate account**
   or **Reactivate account**, and **Block reactivation** or **Allow reactivation**, each
   with a line under it saying what it does. A donor's record leaves this card out.

**Password**
   **Send password reset**, which a donor's record leaves out.

**History**
   Every change to the account's roles and status, newest first, one a line: when, who,
   and what, such as *10/04/2026 at 3:12 PM · Nina Kowalski · gave DART leader* or *…
   blocked reactivation*. It records an account an administrator created on
   :doc:`new-member`, each role given or taken away, and each deactivation, reactivation,
   block, and lifted block, including the person's own. A change made from the server's
   command line reads *The system*, and one by an administrator whose account has since
   been deleted *A deleted account*. With none it reads *No change to this account's
   roles or status is recorded.*

Nothing is saved until you press **Save changes**, and the message *Account saved.* confirms
it. A refused save takes you to what the site refused. **Cancel** puts every box back the
way the account has it and clears the refusal.


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


An address that bounces
=======================

When another mail server refuses an email to this address for good, because the address does
not exist or no longer takes mail, the hint under **Email address** reads
**Bounced**, beside a red dot, with the date (MM/DD/YYYY), followed by the reason that server gave, such as
*5.1.1 550 User unknown*. The bounce check finds these every hour (:doc:`scheduled`), and
:doc:`users` lists every bounced account under **Email**.

Ask the person for an address that works and enter it: a new address clears the flag. So
does the person following a verification or password reset link sent to the address, since
that proves mail reaches it. When you know the address works without changing it (the
person's mailbox was full and they have emptied it, say), press **Clear bounce** under the
address. It asks first; press **Yes, clear bounce** to confirm, or **Cancel**. The message
*Bounce cleared.* confirms it. If the next email to the address bounces too, the flag comes
back.


Granting and removing roles
===========================

#. Find the account on :doc:`users` and open it.
#. Under **Roles**, check the roles they should have and uncheck the ones they should not.
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
  site. Grant it sparingly. Only a system administrator can grant or remove it, so the box
  is grayed out for anybody else.
- A role change takes effect on the person's next visit to a page.


Rules the site enforces
=======================

- **You cannot deactivate or block your own account.** Your own record's **Account
  status** card says so and offers no action.
- **Only a system administrator may grant or remove System administrator.** You can change
  every other role on a system administrator's account.
- **The email address and the account's status are guarded.** You can change the address,
  deactivate, reactivate, or block an account only when you hold every role it holds, since
  moving somebody's address is enough to take their account over. As a user administrator you can move an ordinary member's address, or
  another user administrator's, and nobody else's with a role you lack. Because granting
  roles is your job, you can lift this for any role except System administrator: check the
  missing role on your own record, save, and make the change. Names are never guarded.

Some accounts, typically the one the site was installed with, hold full system access
without the System administrator role checked. They count as a system administrator here, so
only a system administrator can change their roles. Leave their boxes as you found them and
the rest of the form still saves.


Deactivating and reactivating
=============================

Each action on the **Account status** card asks first: pressing it opens a short
explanation below the card's buttons, with a button to go ahead and **Cancel**. Escape
cancels too. A refusal appears in the card.

**Deactivate account** does everything the person's own deactivation from their profile
does. The account's password no longer signs it in, and it is signed out everywhere at once.
Their automatic renewal and any recurring donation are canceled, and they are emailed that it
is off. Any membership term with time left is set aside until they come back. Nothing is
deleted: the profile, the membership history, and the payments stay as they were. An
account administrator has the same action on the **Delete or deactivate** tab of the
:doc:`member-record`.

**Reactivate account** brings a deactivated account back as the person's own reactivation
would: they can sign in again, and a membership set aside when the account was deactivated
resumes, or reads expired if its end date passed meanwhile. Automatic renewal stays off.

The person can also come back on their own. Signing in with the right password tells them
*This account is deactivated. You can reactivate it.* and offers **Reactivate my account**,
and completing a password reset they asked for reactivates it too.

Deactivation is the right step for someone who has left. It does not keep out somebody who
knows the password, so for an account you think has been taken over, deactivate it and ask
the owner to reset the password once they are back in. Deleting an account is an account
administrator's job, on the **Delete or deactivate** tab of the :doc:`member-record`; the person's
payments stay in the books under the name **Deleted member** and the account's number.
That name belongs to a deactivated account, so the :doc:`users` list shows it only when
**Account status** includes deactivated accounts. Its record cannot be changed: pressing
**Save changes** on it is answered *This record keeps a deleted member's payments in the
books and cannot be changed.*


Blocking reactivation
=====================

To keep a deactivated account deactivated, so that the person cannot bring it back, press
**Block reactivation** and confirm. On an active account it deactivates the account first,
exactly as **Deactivate account** does. While the block holds:

- signing in with the right password, or pressing **Reactivate my account**, is answered
  *This account has been closed. Contact CalDART to reopen it.*, with your organization's
  name in place of CalDART;
- asking for a password reset sends no email, and a reset link sent before the block is
  answered with the same sentence;
- registering again with the same address is answered with the same sentence;
- nobody can press **Reactivate account**, here or on the :doc:`member-record`.

Only a user administrator blocks an account or lifts the block. **Allow reactivation** lifts
it and leaves the account deactivated: the person can then reactivate it themselves, or you
can press **Reactivate account**. Both changes are recorded under your name, in the
**History** card.


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

*Only a system administrator can grant or take away the System administrator role.* means
you changed a box on an account with full system access; put the boxes back and save, or
ask a system administrator. *You cannot change the email address of
an account that holds roles you do not hold.*, *You cannot activate or deactivate an
account that holds roles you do not hold.*, and *You cannot block or unblock an account that
holds roles you do not hold.* mean the account holds a role you lack; check it on your own
record, save, and try again. If the address will not save, another account
already uses it, and you have probably found a duplicate. *That account is deactivated, so
no reset email was sent.* means the account was deactivated while the page was open; reload
and reactivate it first. *That account is already deactivated.* and *That account is
already active.* mean somebody changed it while the page was open; reload the page. *The mail
server did not accept the message. A system administrator can see the attempt on the Sent
Emails page.* after **Send password reset** or **Resend verification message** means nothing
was sent: the site could not hand the email to its mail server. A system administrator sees
the attempt marked *Failed:* on **Sent emails**, with the reason; tell whoever runs the
server, and press the button again once it is fixed. If somebody still cannot see a page after you checked its role, ask
them to reload the portal, and check that you pressed **Save changes**. Profiles,
memberships, and payments are not on this screen; they belong to an account administrator.
