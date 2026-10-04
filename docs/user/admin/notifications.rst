:roles: account_admin

=============
Notifications
=============

**Notifications** says who is emailed when something happens, such as a sign-up, a payment,
or a refund, and which events each address hears about. A notification is a short email sent the moment
something happens: somebody signs up, a friend becomes a member, a donation arrives, an
account is deactivated, or an aircraft changes. Each email address you subscribe hears
about the events you pick for it, and nothing else.

An account administrator finds it under **Administration** in the menu. A system
administrator can open it too.


Notification emails
===================

The **Notification emails** card lists every address that gets notifications, one per line:

- **Recipient**: the account's name, or the bare address for somebody outside CalDART.
- **Events**: every event it hears about, joined with commas, the whole list in the row.
- **Active**: *Active* beside a green dot while its emails go out, and *Paused* beside a gray
  one while it is paused.

Each row carries three controls, last on the line under an **Actions** heading a screen
reader announces. A message in the corner of the screen says what the last two did.
**Events** never narrows below a readable width, and its list wraps onto as many lines as it
needs: on a phone the table scrolls sideways, says so above it, and keeps **Recipient**
pinned at the left.

**Edit**
   Opens the subscription's form under the table, to change its events, as **Changing one**
   below describes.

**Pause** and **Resume**
   A paused subscription keeps its events and sends nothing until you resume it. Resuming
   one whose account no longer holds a role that may receive one of its events is refused,
   and the message says why.

**The trashcan**
   Asks first: press it and it turns into **Delete** and **Cancel**. Press **Delete** and
   the address is gone; **Cancel**, Escape, or a click elsewhere leaves it as it is.

With none set up the table reads *No address gets notifications yet*.


Setting one up
~~~~~~~~~~~~~~

**Add an address** opens the form under the table and takes you to its first box:

#. **Recipient email** is where the emails go. Each address has one subscription.
#. The events come in five groups: **Membership**, **Money**, **Accounts**,
   **Aircraft**, and **Callouts**. Check each event the address should hear about; rest the pointer on one to
   read what it covers. **Select all** checks every event in its group, and **Clear**
   unchecks them.

Press **Add address**, or **Cancel** or Escape. *Address added.* confirms a save. An address
that already has a subscription is refused with *This address already has a subscription.*
Edit that one instead. An address that belongs
to a CalDART account is refused when the account holds no role that may receive a checked
event, with a line under the events naming the first such event. An address no account
holds is refused until you check **This address is outside CalDART and may receive these
notifications**, which appears once CalDART asks for it.


Changing one
~~~~~~~~~~~~

**Edit** on a row opens the same form, headed **Edit notifications**, with the subscription's
events checked. The **Recipient** is shown as plain text, since it cannot change: to send the
notifications somewhere else, delete the subscription and set up another. Change the checked events
and press **Save changes**; the form closes, *Address saved.* confirms it, and the row shows the
change. **Cancel**, or Escape, closes the form and changes nothing, and you are back on the
row's **Edit**. One form is open at a time.


Who may receive what
====================

Each event may go to the holders of certain roles, and a system administrator may receive
every one:

- **Membership** events go to an account administrator or a user administrator.
- **Money** events go to the treasurer or an account administrator.
- **Accounts** events go to a user administrator or an account administrator.
- **Aircraft** events go to an account administrator.
- **Callouts** events go to CalDART management or a DART leader. A DART leader hears only
  of the callouts they sent or that went to their own DART.

CalDART checks each time it sends. When an account has lost the role, or has been
deactivated, it is skipped for that event and hears nothing; its subscription stays as it
is and needs no attention. An address no account holds receives every event it is
subscribed to. When somebody later makes an account with that address, the account's roles
decide from then on.


The events
==========

Each email's subject is the organization's name and a one-line headline, such as
*CalDART: Pat Pilot signed up as a friend*. The email gives a few labeled lines and one
link, to the member's record, the user's record, the payment, or the aircraft. A system
administrator sees each one on the :doc:`sent-emails` page under the purpose
shown in italics below.

Membership
~~~~~~~~~~

*Notification: Sign-up*
   Somebody registers on the site. It gives their email, their DART, and whether they
   joined as a member or a friend. When they chose a DART, the email also goes to each of
   that DART's people checked **Roster** on the :doc:`darts` screen, subscribed or not.
*Notification: Member added by an administrator*
   An account administrator adds somebody on :doc:`new-member`. It names who added them.
*Notification: Member became a friend*
   A member becomes a friend, and says how: they chose it, their membership lapsed, or an
   administrator changed it.
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
   Somebody turns on automatic renewal or a recurring donation; the email says which. It
   gives the plan or amount, how often, and the next charge.
*Notification: Automatic renewal or recurring donation turned off*
   An automatic renewal or recurring donation stops, and says whether the person, an
   administrator, a lapse, a deactivation, or the account's deletion stopped it. When
   the account was deleted, the email has no link, because the record is gone.
*Notification: Automatic renewal or recurring donation charge failed*
   An automatic charge is declined. It gives the reason and when it is tried again.
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
   A user administrator grants or takes away a role. It lists the roles added, removed, and
   held now.
*Notification: Email address changed*
   Somebody confirms a changed email address. It gives the old and the new address.
*Notification: Profile changed*
   A profile is edited, by its holder or by an administrator. It names the fields that
   changed. An edit that changes nothing sends nothing.
*Notification: Verification recorded*
   A verifier verifies or clears a member's pilot certificate, medical, or photo ID, or an
   aircraft's insurance. One email covers everything verified or cleared in one save. It
   lists what was verified, what was cleared, and who did it, and links the member's
   record or the aircraft. A change a member makes to their own details clears the
   verification without this email: *Notification: Profile changed* or *Notification:
   Aircraft changed* covers it.

Aircraft
~~~~~~~~

*Notification: Aircraft added*
   An aircraft is added to a member's list, by N-number and owner.
*Notification: Aircraft changed*
   An aircraft's details change. It names the fields that changed.
*Notification: Aircraft removed*
   An aircraft is taken off a member's list. This email carries no link.

Callouts
~~~~~~~~

*Notification: Callout answer*
   Somebody answers a mission callout, or changes their answer. It names the person, their
   answer and note, the callout, and their DART, and links the callout's answers on
   :doc:`../bulk-email/callouts`.


If something looks wrong
========================

If an address stops hearing about an event, look at its **Active** column: *Paused* means
the subscription is paused, and **Resume** says whether the account may still receive every
event on it. An account that lost a role or was deactivated is skipped quietly, so check
its roles on the **Users and roles** screen. If a notification never arrives, a system
administrator can find it on the :doc:`sent-emails` page and see whether the
mail server refused it.
