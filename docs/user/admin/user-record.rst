:roles: user_admin

===========
User record
===========

The **user record** shows one account as a user administrator sees it: the state of its
membership, the roles it holds, whether it can sign in, and the buttons that send a password
reset link or require a new password. You change roles and the account's status here, but
not the name or the address. Open it by clicking a name on :doc:`users`.


What you see
============

The person's name heads the page, with their address under it and **Back to Roles and
status** beside it. Six cards follow.

**Membership**
   The kind of account (**Member**, **Friend**, or **Donor**), the membership status, and
   *Profile complete* or *Profile incomplete*. A member without a term in force shows *Not
   yet paid* (or *No membership in force*), or *Membership set aside while deactivated*, as
   on the :doc:`member-record`. A donor's card adds *A donor gave through the public site and
   cannot sign in. If a receipt went astray, an account administrator corrects the email
   address on the member record.* If you are also an account administrator, **Member
   record** opens the person's :doc:`member-record`, where you can delete a donor.

**Roles**
   First, a line with **Email address:** and then **Verified** with a date, or
   **Unverified**, and **Bounced**, beside a red dot, if the address bounces. The address
   itself is at the top of the page. It is changed on the :doc:`member-record` or by the
   person (*Waiting for … to confirm.* marks a change that is waiting), never here, and the
   same goes for the name. Then comes a box for each role, with a line saying what it
   allows. A box you can't change is grayed out, and its line says why. Unless you are a
   system administrator, the **System administrator** box is grayed out, with *Only a system
   administrator can give or take away this role.* So is the box of each two-factor role
   you don't hold yourself (:doc:`../roles`), with *Only somebody who holds this role, or a
   system administrator, can give or take it away.* On your own record, the card lists your
   roles under **Your roles**, without boxes or **Save changes**, and says *You cannot
   change your own roles. Ask another administrator.*

**Account status**
   Whether the account can sign in, and the actions that change it: **Deactivate account**
   or **Reactivate account**, and **Block reactivation** or **Allow reactivation**. Each
   has a line under it saying what it does. A donor's record leaves this card out.

**Two-factor sign-in**
   **On**, beside a green dot, if the person has an authenticator app set up, or **Off**,
   beside a gray one, if not. While it is on, **Reset two-factor** is for somebody who has
   lost both their phone and their backup codes. It asks first, and **Yes, reset
   two-factor** goes ahead; :doc:`../member/two-factor` says what happens then. Only a
   system administrator can reset a system administrator's two-factor sign-in. For anybody
   else the button is grayed out, with the reason under it. A donor's record leaves this
   card out, and on your own record it says *Change your own two-factor sign-in on your
   profile.*

**Password**
   **Send password reset** and **Require a new password**, which a donor's record leaves
   out; :doc:`user-password` covers both. On your own record, the card says only *To change
   your own password, use Change password.*

**History**
   Every change to the account's roles, status, and address, newest first, one to a line:
   when, who, and what, such as *10/04/2026 at 3:12 PM · Nina Kowalski · gave DART leader*.
   It records an account an administrator created on :doc:`new-member`, and each role given
   or taken away. It also records each deactivation, reactivation, block, and lifted block,
   each new password required, each change of address confirmed or undone, and each
   two-factor reset. A change made by a command on the server shows *The system*, and one
   made by a deleted administrator shows *A deleted account*. If the history is empty, it
   says *No change to this account's roles or status is recorded.*

Role changes are saved only when you press **Save changes**, and *Account saved.* confirms
it. If the site refuses a save, it takes you to what it refused. **Cancel** puts every box
back the way the account has it and clears the refusal.


A name or an address
====================

The user record shows the name and the address, but you can't change them here. An account
administrator corrects a misspelled name, or moves an account to a new address, on the
:doc:`member-record`. People change their own name on their profile, and their own address
from **Change email** in the portal's menu.

If the address is unverified, a **Resend verification message** button sends a fresh link,
and the message at the top of the screen names the address it went to. The button is
disabled on a deactivated account. Clicking the link a second time is harmless, so send
another whenever somebody says the first never came.


An address that bounces
=======================

Another mail server may refuse an email to this address for good, because the address
doesn't exist or has stopped taking mail. Then the hint under **Email address** says
**Bounced**, beside a red dot, with the date (MM/DD/YYYY) and the reason that server gave,
such as *5.1.1 550 User unknown*. The bounce check finds these every hour
(:doc:`scheduled`), and :doc:`users` lists every bounced account under **Email**.

Ask the person for an address that works. A new address, entered on the
:doc:`member-record` or by the person, clears the flag. So does the person following a
verification or password reset link sent to the address, since that proves mail reaches it.
If you know the address works and doesn't need changing (say the person's mailbox was full
and they have emptied it), press **Clear bounce** under the address. It asks first; press
**Yes, clear bounce** to confirm, or **Cancel**. *Bounce cleared.* confirms it. If the next
email to the address bounces too, the flag comes back.


Granting and removing roles
===========================

#. Find the account on :doc:`users` and open it.
#. Under **Roles**, check the roles they should have and uncheck the ones they shouldn't.
#. Press **Save changes**.
#. Ask them to reload the portal, so their menu shows the change.

Things worth knowing:

- Roles add up. **Member** doesn't open a screen of its own, because every signed-in
  account has the member screens.
- **Treasurer** opens the payment screens, but nothing that shows a member's medical or
  certificate. A volunteer who keeps the books doesn't need to see anybody's medical
  details.
- **Website administrator** opens the website's editor. Granting the role is all you need
  to do, and removing it closes the editor again.
- **System administrator** can do everything, including the server's own administration
  site. Grant it sparingly. Only a system administrator can grant or remove it, so the box
  is grayed out for anybody else.
- You can grant or remove the other two-factor roles (User administrator, Treasurer, Account
  administrator, CalDART management, and Website administrator) only if you hold that role
  yourself. For the rest, ask a system administrator or somebody who holds the role.
- A role change takes effect the next time the person opens a page.
- An account administrator can have every role change emailed to you, or to anybody else
  allowed to get it, as the **Roles changed** notification (:doc:`notifications`).


Rules the site enforces
=======================

- **You cannot deactivate or block your own account, or reset its password.** Your own
  record's **Account status** card says so and doesn't offer any action, and its
  **Password** card points you to **Change password**.
- **Nobody changes their own roles**, even a system administrator. Your own record lists
  your roles without boxes, so ask another administrator to change them. If you try anyway,
  the site refuses and records the attempt.
- **Only a system administrator may grant or remove System administrator.**
- **A two-factor role is granted or removed only by somebody who holds it**, or by a system
  administrator. Any user administrator can grant and remove Member, Verifier, and DART
  leader on any account, even a system administrator's. If a save would change a role you
  aren't allowed to change, the site refuses the whole save and names the role: *You cannot
  give or take away a role you do not hold yourself: Treasurer.*
- **The account's status is protected.** You can deactivate, reactivate, or block an
  account, send it a password reset, or require a new password, only if you hold every
  two-factor role it holds (:doc:`../roles`). Member, Verifier, and DART leader don't count.
  As a user administrator, you can act on an ordinary member, a DART leader, a verifier, or
  another user administrator. You can't act on anybody else with a two-factor role you lack.

Some accounts, usually the one the site was installed with, have full system access without
the System administrator box checked. They count as a system administrator here, so only a
system administrator can change their roles. Leave their boxes as you found them, and the
rest of the form still saves.


Deactivating and reactivating
=============================

Each action on the **Account status** card asks first. Pressing it opens a short
explanation below the card's buttons, with a button to go ahead and **Cancel**. Escape
cancels too. If the site refuses, the reason appears in the card.

**Deactivate account** does everything the person's own deactivation from their profile
does. The account's password stops signing it in, and it is signed out everywhere at once.
Their automatic renewal and any recurring donation are canceled, and they get an email
saying it is off. Any membership term with time left is set aside until they come back.
Nothing is deleted: the profile, the membership history, and the payments stay as they
were. An account administrator has the same action on the **Delete or deactivate** tab of
the :doc:`member-record`.

**Reactivate account** brings a deactivated account back, just as the person's own
reactivation would. They can sign in again, and a membership set aside when the account was
deactivated picks up again, or shows as expired if its end date passed in the meantime.
Automatic renewal stays off.

The person can also come back on their own. If they sign in with the right password, the
site tells them *This account is deactivated. You can reactivate it.* and offers
**Reactivate my account**. Completing a password reset they asked for reactivates it too.

Deactivation is for someone who has left. It doesn't keep out somebody who knows the
password, because they can sign in and reactivate the account. For that, use
:ref:`user-record-new-password`. Deleting an account is an account administrator's job, on
the **Delete or deactivate** tab of the :doc:`member-record`. The person's payments stay in
the books under the name **Deleted member** and the account's number. That name belongs to
a deactivated account, so the :doc:`users` list shows it only when **Account status**
includes deactivated accounts. You can't change its record. If you press **Save changes**
on it, the site answers *This record keeps a deleted member's payments in the books and
cannot be changed.*


Blocking reactivation
=====================

To keep a deactivated account deactivated, so that the person can't bring it back, press
**Block reactivation** and confirm. On an active account, it deactivates the account first,
exactly as **Deactivate account** does. While the block is on:

- if the person signs in with the right password, or presses **Reactivate my account**, the
  site answers *This account has been closed. Contact CalDART to reopen it.*, with your
  organization's name instead of CalDART;
- if they ask for a password reset, the site doesn't send an email, and a reset link sent
  before the block gets the same answer;
- if they register again, the site doesn't open an account, and emails them that the
  account is closed;
- nobody can press **Reactivate account**, here or on the :doc:`member-record`.

Only a user administrator can block an account or lift the block. **Allow reactivation**
lifts it and leaves the account deactivated, for you or the person to reactivate. The
**History** card records both changes under your name.


If something looks wrong
========================

*Only a system administrator can grant or take away the System administrator role.* means
you changed a box on an account with full system access. Put the boxes back and save, or
ask a system administrator. *You cannot give or take away a role you do not hold yourself:*
followed by role names means the save changed a two-factor role you don't hold. Put that
box back and save, or ask a system administrator or somebody who holds the role. *You
cannot change your own roles. Ask another administrator.* means just that. These four mean
the account holds a two-factor role you lack: *You cannot activate or deactivate an account
that holds administrative roles you do not hold.*, *You cannot block or unblock an account
that holds administrative roles you do not hold.*, *You cannot send a password reset to an
account that holds administrative roles you do not hold.*, and *You cannot require a new
password for an account that holds administrative roles you do not hold.* Ask a system
administrator, or a colleague who holds every two-factor role that account holds.

*That account is deactivated, so no reset email was sent.* means somebody deactivated the
account while you had the page open. Reload, and reactivate it first. *That account is
already deactivated.* and *That account is already active.* mean somebody changed it while
you had the page open; reload the page. *The mail server did not accept the message. A
system administrator can see the attempt on the "Sent emails" page.* can follow **Send
password reset** or **Resend verification message**. It means the site couldn't hand the
email to its mail server, so the email wasn't sent. A system administrator sees the attempt
marked *Failed:* on **Sent emails**, with the reason. Tell whoever runs the server, and
press the button again once it is fixed. After **Require a new password**, the message says
the old password is shut out even though the email failed. Pressing the button again sends
a fresh link. If somebody still can't see a page after you checked its role, ask them to
reload the portal, and make sure you pressed **Save changes**. Profiles, memberships, and
payments aren't on this screen; they belong to an account administrator.
