=============
Notifications
=============

**Notifications** is where you choose who hears about what happens in CalDART. A
notification is a short email sent the moment something happens: somebody signs up, a
friend becomes a member, a donation arrives, an account is deactivated, or an aircraft
changes. Each email address you subscribe hears about the events you pick for it, and
nothing else.

An account administrator finds it under **Administration** in the menu. A system
administrator can open it too.


Who hears about what
====================

The **Who hears about what** card lists every subscription, one per line:

- **Recipient**: the account's name, or the bare address for somebody outside CalDART.
- **Events**: the events it hears about, joined with commas. A long list is cut short;
  rest the pointer on it to read the whole list.
- **Active**: a green dot while its emails go out, and a gray one while it is paused.

Each row carries three controls. The line above the table says what the last two did.

**Edit**
   Opens the subscription's form under the table, to change its events, as **Changing one**
   below describes.

**Pause** and **Resume**
   A paused subscription keeps its events and sends nothing until you resume it. Resuming
   one whose account no longer holds a role that may receive one of its events is refused,
   and the line says why.

**The trashcan**
   Deletes the subscription.

With none set up the table reads *Nobody is subscribed to a notification yet*.


Setting one up
~~~~~~~~~~~~~~

**New subscription** opens the form under the table:

#. **Recipient email** is where the emails go. Each address has one subscription.
#. The events come in four groups: **Membership**, **Money**, **Accounts**, and
   **Aircraft**. Tick each event the address should hear about; rest the pointer on one to
   read what it covers. **Select all** ticks every event in its group, and **Clear**
   unticks them.

Press **Save**, or **Cancel**. An address that already has a subscription is refused with
*This address already has a subscription.* Edit that one instead. An address that belongs
to a CalDART account is refused when the account holds no role that may receive a ticked
event, with a line under the events naming the first such event. An address no account
holds is refused until you tick **This address is outside CalDART and may receive these
notifications**, which appears once CalDART asks for it.


Changing one
~~~~~~~~~~~~

**Edit** on a row opens the same form, headed **Edit subscription**, with the subscription's
events ticked. The **Recipient** is shown as plain text, since it cannot change: to send the
notifications somewhere else, delete the subscription and set up another. Change the ticks
and press **Save**; the form closes and the row shows the change. **Cancel** closes the form
and changes nothing. One form is open at a time.


Who may receive what
====================

Each event may go to the holders of certain roles, and a system administrator may receive
every one:

- **Membership** events go to an account administrator or a user administrator.
- **Money** events go to the treasurer or an account administrator.
- **Accounts** events go to a user administrator or an account administrator.
- **Aircraft** events go to an account administrator.

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
administrator sees each one in the email log on the :doc:`system` page under the purpose
shown in italics below.

Membership
~~~~~~~~~~

*Notification: Sign-up*
   Somebody registers on the site. It gives their email, their DART, and whether they
   joined as a member or a friend. When they chose a DART, the email also goes to each of
   that DART's people ticked **Roster** on the :doc:`darts` screen, subscribed or not.
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

*Notification: Automatic payment turned on*
   Somebody turns on automatic renewal or a recurring donation; the email says which. It
   gives the plan or amount, how often, and the next charge.
*Notification: Automatic payment turned off*
   An automatic renewal or recurring donation stops, and says whether the person, an
   administrator, a lapse, or a deactivation stopped it.
*Notification: Automatic payment declined*
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
   aircraft's insurance. One email covers everything verified or cleared in one save.

Aircraft
~~~~~~~~

*Notification: Aircraft added*
   An aircraft is added to a member's list, by N-number and owner.
*Notification: Aircraft changed*
   An aircraft's details change. It names the fields that changed.
*Notification: Aircraft removed*
   An aircraft is taken off a member's list. This email carries no link.


If something looks wrong
========================

If an address stops hearing about an event, look at its **Active** dot: a gray one means
the subscription is paused, and **Resume** says whether the account may still receive every
event on it. An account that lost a role or was deactivated is skipped quietly, so check
its roles on the **Users & roles** screen. If a notification never arrives, a system
administrator can find it in the email log on the :doc:`system` page and see whether the
mail server refused it.
