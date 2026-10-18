:roles: account_admin

===================
Notification emails
===================

**Notification emails** says who gets an email when something happens, such as a sign-up,
a payment, or a refund, and which events each address hears about. A notification is a
short email sent the moment something happens: somebody signs up, a friend becomes a
member, a donation arrives, an account is deactivated, or an aircraft changes. Each address
you subscribe hears only about the events you pick for it.

An account administrator finds it under **Administration** in the menu. A system
administrator can open it too.


Notification emails
===================

The **Notification emails** card lists every address that gets notifications, one per line:

- **Recipient**: the account's name, or just the address for somebody outside CalDART.
- **Events**: every event it hears about, separated by commas, with the whole list in the
  row.
- **Active**: *Active* beside a green dot while its emails go out, and *Paused* beside a gray
  one while it is paused.

Each row has three controls at the end of the line, under an **Actions** heading that a
screen reader announces. A message in the corner of the screen says what the last two did.
The **Events** column never gets too narrow to read, and its list wraps onto as many lines
as it needs. On a phone, the table scrolls sideways, says so above it, and keeps
**Recipient** pinned at the left.

**Edit**
   Opens the subscription's form under the table, so you can change its events, as
   **Changing one** below describes.

**Pause** and **Resume**
   A paused subscription keeps its events, but it doesn't send anything until you resume
   it. If the account has since lost a role that one of its events needs, CalDART refuses
   to resume it, and the message says why.

**The trashcan**
   Asks first: press it, and it turns into **Delete** and **Cancel**. Press **Delete** to
   remove the address. **Cancel**, Escape, or a click elsewhere leaves it as it is.

Until you set one up, the table says *No address gets notifications yet*.


Setting one up
~~~~~~~~~~~~~~

**Add an address** opens the form under the table and puts you in its first box:

#. **Recipient email** is where the emails go. Each address has one subscription.
#. The events come in five groups: **Membership**, **Money**, **Accounts**, **Aircraft**,
   and **Callouts**. Check each event the address should hear about. Rest the pointer on
   an event to see what it covers. **Select all** checks every event in its group, and
   **Clear** unchecks them.

Press **Add address**, or **Cancel** or Escape. *Address added.* confirms a save. If the
address already has a subscription, CalDART refuses it with *This address already has a
subscription.* Edit that one instead. If the address belongs to a CalDART account, and the
account doesn't hold a role allowed to get one of the checked events, CalDART refuses it.
A line under the events names the first such event. If the address doesn't belong to an
account, CalDART refuses it until you check **This address is outside CalDART and may
receive these notifications**. That box appears once CalDART asks for it.


Changing one
~~~~~~~~~~~~

**Edit** on a row opens the same form, headed **Edit notifications**, with the
subscription's events checked. The **Recipient** is shown as plain text, because you can't
change it. To send the notifications somewhere else, delete the subscription and set up
another one. Change the checked events and press **Save changes**. The form closes,
*Address saved.* confirms it, and the row shows the change. **Cancel**, or Escape, closes
the form without changing anything, and you land back on the row's **Edit**. Only one form
is open at a time.


Who may receive what
====================

Each event may go only to people who hold certain roles. A system administrator may get
every event:

- **Membership** events go to an account administrator or a user administrator.
- **Money** events go to the treasurer or an account administrator.
- **Accounts** events go to a user administrator or an account administrator.
- **Aircraft** events go to an account administrator.
- **Callouts** events go to CalDART management or a DART leader. A DART leader hears only
  about the callouts they sent or that went to their own DART.

CalDART checks every time it sends. If an account has lost the role, or has been
deactivated, CalDART skips it for that event. Its subscription stays as it is, and you
don't need to do anything about it. An address that doesn't belong to an account gets
every event it is subscribed to. If somebody later makes an account with that address, the
account's roles decide from then on.


The events
==========

Each email's subject is the organization's name and a one-line headline, such as
*CalDART: Pat Pilot signed up as a friend*. The email has a few labeled lines and one link,
to the member's record, the user's record, the payment, or the aircraft. A system
administrator can find each one on the :doc:`sent-emails` page, under the purpose shown in
italics below.

Membership
~~~~~~~~~~

*Notification: Sign-up*
   Somebody registers on the site. It gives their email, their DART, and whether they
   joined as a member or a friend. If they chose a DART, the email also goes to each of
   that DART's people with **Roster** checked on the :doc:`darts` screen, subscribed or
   not.
*Notification: Member added by an administrator*
   An account administrator adds somebody on :doc:`new-member`. It names who added them.
*Notification: Member became a friend*
   A member becomes a friend. The email says how: they chose it, their membership lapsed,
   or an administrator changed it.
*Notification: Friend became a member*
   A friend becomes a member by paying, by a granted term, or by an administrator's change.
*Notification: Membership paid*
   A payment starts or extends a membership, paid by hand or renewed automatically. It
   gives the plan, the amount, the date it runs to, and any contribution.
*Notification: Membership granted by an administrator*
   An account administrator grants a term on the :doc:`member-record`. It gives the plan and
   the date it runs to.
*Notification: Membership expired*
   A membership runs out.

Money
~~~~~

*Notification: Automatic renewal or recurring donation turned on*
   Somebody turns on automatic renewal or a recurring donation, and the email says which.
   It gives the plan or amount, how often, and the next charge.
*Notification: Automatic renewal or recurring donation turned off*
   An automatic renewal or recurring donation stops. The email says what stopped it: the
   person, an administrator, a lapse, a deactivation, or the account's deletion. If the
   account was deleted, the email doesn't have a link, because the record is gone.
*Notification: Automatic renewal or recurring donation charge failed*
   An automatic charge is declined. It gives the reason and when the charge will be tried
   again.
*Notification: Automatic charge needs checking*
   An automatic charge may have gone through but PayPal can't say, or a charge has been
   waiting at the payment service for more than three days. It gives the amount and the
   reason. The treasurer or an account administrator settles it on
   :doc:`../finance/renewals`. The email comes again if the membership runs out while the
   charge is still waiting. The treasurer, account administrators, and the system
   administrator can subscribe.
*Notification: Donation received*
   A gift arrives: a public donation, a contribution on its own, or a recurring donation.
   A contribution paid with a membership is part of *Notification: Membership paid*.
*Notification: Payment recorded by hand*
   The treasurer records a check or cash payment. It gives the method and what it paid for.
*Notification: Payment refunded*
   A payment is refunded, in whole or in part. It gives the amount, who refunded it, and
   whether the membership was canceled.

Accounts
~~~~~~~~

*Notification: Account deactivated*
   An account is deactivated, by its holder or by an administrator; the email says which.
*Notification: Account reactivated*
   A deactivated account is brought back.
*Notification: Roles changed*
   Any account's roles change, whoever or whatever changed them. It might be a user
   administrator or a system administrator on the user record, or a DART leader or user
   administrator making somebody a verifier from the member check. It might also be a
   command run on the server, such as the one that sets up the first system administrator.
   The headline names who made the change (*A command on the server* for a command) and
   whose roles changed. The email lists the roles added, the roles removed, and the roles
   the account holds after the change.
*Notification: Email address changed*
   Somebody confirms a changed email address. It gives the old and the new address.
*Notification: Profile changed*
   A profile is edited, by its holder or by an administrator. It names the fields that
   changed. An edit that doesn't change anything doesn't send an email.
*Notification: Verification recorded*
   A verifier verifies or clears a member's pilot certificate, medical, or photo ID, or an
   aircraft's insurance. One email covers everything verified or cleared in one save. It
   lists what was verified, what was cleared, and who did it, and links to the member's
   record or the aircraft. When a member changes their own details, the verification is
   cleared without this email. *Notification: Profile changed* or *Notification: Aircraft
   changed* covers it instead.

Aircraft
~~~~~~~~

*Notification: Aircraft added*
   An aircraft is added to a member's list, by N-number and owner.
*Notification: Aircraft changed*
   An aircraft's details change. It names the fields that changed.
*Notification: Aircraft removed*
   An aircraft is taken off a member's list. This email doesn't have a link.

Callouts
~~~~~~~~

*Notification: Callout answer*
   Somebody answers a mission callout, or changes their answer. It names the person, their
   answer and note, the callout, and their DART, and links to the callout's answers on
   :doc:`../bulk-email/callouts`.


If something looks wrong
========================

If an address stops hearing about an event, look at its **Active** column. *Paused* means
the subscription is paused, and **Resume** tells you whether the account may still get
every event on it. CalDART quietly skips an account that has lost a role or been
deactivated, so check its roles on the **Roles and status** screen. If a notification never
arrives, a system administrator can find it on the :doc:`sent-emails` page and see whether
the mail server refused it.
