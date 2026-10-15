:roles: user_admin

===========
User record
===========

The **user record** is one account seen by a user administrator: where its membership
stands, the roles it holds, whether it can sign in, and the buttons that send a password
reset link or require a new password. Roles and the account's status are changed here; the
name and the address are not. Open it by clicking a name on :doc:`users`.


What you see
============

The person's name heads the page, with their address under it and **Back to Roles and
status** beside it. Six cards follow.

**Membership**
   The kind of account (**Member**, **Friend**, or **Donor**), the membership status, and
   *Profile complete* or *Profile incomplete*. A member with no term in force reads *Not yet
   paid* (or *No membership in force*), or *Membership set aside while deactivated*, as on
   the :doc:`member-record`. A donor's card adds *A donor gave through the public site and
   cannot sign in. If a receipt went astray, an account administrator corrects the email
   address on the member record.* If you are an account administrator too, **Member record**
   opens the person's :doc:`member-record`, where a donor can be deleted.

**Roles**
   A line that reads **Email address:** and then **Verified** with a date, or
   **Unverified**, and **Bounced**, beside a red dot, when the address bounces. The address
   itself is at the top of the page, changed on the :doc:`member-record` or by the person
   (*Waiting for … to confirm.* marks a change waiting), never here, as is the name. Then a
   box for each role with a line saying what it grants. A box you may not change is grayed
   out, and its line says why. Unless you are a system administrator, the **System
   administrator** box is one, with *Only a system administrator can give or take away this
   role.* So is the box of each two-factor role you do not hold yourself (:doc:`../roles`),
   with *Only somebody who holds this role, or a system administrator, can give or take it
   away.* On your own record the card lists the roles you hold under **Your roles**, with no
   boxes and no **Save changes**, and says *You cannot change your own roles. Ask another
   administrator.*

**Account status**
   Whether the account can sign in, and the actions that change it: **Deactivate account**
   or **Reactivate account**, and **Block reactivation** or **Allow reactivation**, each
   with a line under it saying what it does. A donor's record leaves this card out.

**Two-factor sign-in**
   **On** beside a green dot when the person has an authenticator app set up, **Off** beside
   a gray one when not. While it is on, **Reset two-factor** is for somebody who lost both
   their phone and their backup codes: it asks first, and **Yes, reset two-factor** goes
   ahead; :doc:`../member/two-factor` says what happens then. Only a system administrator
   resets a system administrator's, and the button is grayed out for anybody else, with the
   reason under it. A donor's record leaves this card out, and your own reads *Change your
   own two-factor sign-in on your profile.*

**Password**
   **Send password reset** and **Require a new password**, which a donor's record leaves
   out; :doc:`user-password` covers both. On your own record the card reads only *To change
   your own password, use Change password.*

**History**
   Every change to the account's roles, status, and address, newest first, one a line: when,
   who, and what, such as *10/04/2026 at 3:12 PM · Nina Kowalski · gave DART leader*. It
   records an account an administrator created on :doc:`new-member`, each role given or taken
   away, each deactivation, reactivation, block, and lifted block, each new password
   required, each change of address confirmed or undone, and each two-factor reset. The
   command line reads *The system*, a deleted administrator *A deleted account*, and none at
   all *No change to this account's roles or status is recorded.*

No role change is saved until you press **Save changes**, and the message *Account saved.*
confirms it. A refused save takes you to what the site refused. **Cancel** puts every box
back the way the account has it and clears the refusal.


A name or an address
====================

The user record shows the name and the address but does not change them. An account
administrator corrects a misspelled name, or moves an account to a new address, on the
:doc:`member-record`, and people change their own name on their profile and their own
address from **Change email** in the portal's menu.

On an unverified address a **Resend verification message** button sends a fresh link, and
the message at the top of the screen names the address it went to. It is disabled on a
deactivated account. Clicking the link a second time does no harm, so send another whenever
somebody says the first never came.


An address that bounces
=======================

When another mail server refuses an email to this address for good, because the address does
not exist or no longer takes mail, the hint under **Email address** reads **Bounced**,
beside a red dot, with the date (MM/DD/YYYY), followed by the reason that server gave, such
as *5.1.1 550 User unknown*. The bounce check finds these every hour (:doc:`scheduled`), and
:doc:`users` lists every bounced account under **Email**.

Ask the person for an address that works: a new address, entered on the :doc:`member-record`
or by the person, clears the flag. So does the person following a verification or password
reset link sent to the address, since that proves mail reaches it. When you know the address
works without changing it (the person's mailbox was full and they have emptied it, say),
press **Clear bounce** under the address. It asks first; press **Yes, clear bounce** to
confirm, or **Cancel**. The message *Bounce cleared.* confirms it. If the next email to the
address bounces too, the flag comes back.


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
- The other two-factor roles (User administrator, Treasurer, Account administrator, CalDART
  management, and Website administrator) you grant or remove only while you hold the role
  yourself. Ask a system administrator, or somebody who holds the role, for the rest.
- A role change takes effect on the person's next visit to a page.
- An account administrator can have every role change emailed, to you or anybody else
  who may receive it, as the **Roles changed** notification (:doc:`notifications`).


Rules the site enforces
=======================

- **You cannot deactivate or block your own account, or reset its password.** Your own
  record's **Account status** card says so and offers no action, and its **Password** card
  points you to **Change password**.
- **Nobody changes their own roles**, a system administrator included. Your own record
  lists your roles without boxes; ask another administrator to change them. Trying anyway is
  refused, and the attempt is recorded.
- **Only a system administrator may grant or remove System administrator.**
- **A two-factor role is granted or removed only by somebody who holds it**, or by a system
  administrator. Any user administrator grants and removes Member, Verifier, and DART
  leader, on any account, a system administrator's included. A save that would move a role
  you may not move is refused whole, naming the role: *You cannot give or take away a role
  you do not hold yourself: Treasurer.*
- **The account's status is guarded.** You can deactivate, reactivate, or block an account,
  send it a password reset, or require a new password of it, only when you hold every role
  it holds. As a user administrator you can act on an ordinary member, or another user
  administrator, and nobody else with a role you lack.

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

Deactivation is for someone who has left. It does not keep out somebody who knows the
password, who can sign in and reactivate the account; use :ref:`user-record-new-password`
for that. Deleting an account is an account administrator's job, on the **Delete or
deactivate** tab of the :doc:`member-record`; the person's payments stay in the books under
the name **Deleted member** and the account's number. That name belongs to a deactivated
account, so the :doc:`users` list shows it only when **Account status** includes deactivated
accounts. Its record cannot be changed: pressing **Save changes** on it is answered *This
record keeps a deleted member's payments in the books and cannot be changed.*


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
- registering again opens nothing, and the person is emailed that the account is closed;
- nobody can press **Reactivate account**, here or on the :doc:`member-record`.

Only a user administrator blocks an account or lifts the block. **Allow reactivation** lifts
it and leaves the account deactivated, for the person or you to reactivate. Both changes are
recorded under your name, in the **History** card.


If something looks wrong
========================

*Only a system administrator can grant or take away the System administrator role.* means
you changed a box on an account with full system access; put the boxes back and save, or ask
a system administrator. *You cannot give or take away a role you do not hold yourself:* and
the roles it names means the save moved a two-factor role you do not hold; put that box back
and save, or ask a system administrator or somebody who holds the role. *You cannot change
your own roles. Ask another administrator.* means just that. *You cannot activate or
deactivate an account that holds roles you do not hold.*, *You cannot block or unblock an
account that holds roles you do not hold.*, *You cannot send a password reset to an account
that holds roles you do not hold.*, and *You cannot require a new password for an account
that holds roles you do not hold.* mean the account holds a role you lack; ask a system
administrator, or a colleague who holds every role that account holds. *That
account is deactivated, so no reset email was sent.* means the account was deactivated while
the page was open; reload and reactivate it first. *That account is already deactivated.*
and *That account is already active.* mean somebody changed it while the page was open;
reload the page. *The mail server did not accept the message. A system administrator can see
the attempt on the Sent Emails page.* after **Send password reset** or **Resend verification
message** means nothing was sent: the site could not hand the email to its mail server. A
system administrator sees the attempt marked *Failed:* on **Sent emails**, with the reason;
tell whoever runs the server, and press the button again once it is fixed. After **Require a
new password** the message says the old password is shut out regardless; pressing it again
sends a fresh link. If somebody still cannot see a page after you checked its role, ask them
to reload the portal, and check that you pressed **Save changes**. Profiles, memberships,
and payments are not on this screen; they belong to an account administrator.
