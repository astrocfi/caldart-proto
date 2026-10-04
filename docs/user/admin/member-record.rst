:roles: account_admin, dart_leader

=============
Member record
=============

The **member record** is everything CalDART holds about one member, friend, or donor: their
account and profile, their membership terms, their payments, and the controls to remove the
record. Only an account administrator can open it, by clicking a name on :doc:`members` or
on any other screen that lists people. A system administrator can open it too.

A donor, somebody who has only given through the public site, is on no member list. Open a
donor's record from **Member record** on one of their payments (search the
:doc:`../finance/payment-list` for their name, then see :doc:`../finance/payment-record`) or
on their :doc:`../finance/member-ledger`; from their :doc:`user-record` if you are a user
administrator too; or from their name on the **Donors** tab (:doc:`../finance/donors`) if
you are the treasurer too. None of these opens a **Deleted member** record (see `A deleted
member's record`_).


What you see
============

The person's name heads the page, with **Back to members** beside it. A donor's record has
**Back to donors** there instead, which returns to the **Donors** tab, when you have that
tab. A summary strip under the name carries:

- their membership chip: **Current**, **Expiring soon**, **Expired**, **Friend**, or
  **Never expires** for a life member. Somebody who joined as a member and has no term that
  has started, only a canceled one, or only suspended ones reads **Friend**: nobody is a
  member until a paid or granted term has started;
- the plan, the expiry date (left out for a life member), and *joined* with the date their
  first term began;
- *updated* with the date their profile was last changed, or *never edited* for a profile
  nobody has changed since it was loaded. A payment, a renewal, or a membership grant does
  not change the date, so it tells you how current the details are;
- a **Donor** chip for somebody who has only given through the public site, and an
  **Account deactivated** chip for an account that cannot sign in;
- their email address, and the roles the account holds. When another mail server has
  refused an email to the address for good, a red **Bounced** chip with the date and the
  reason that server gave follows it. A user administrator corrects the address or clears
  the flag on the :doc:`user-record`.

Below the strip are four tabs: **Profile**, **Memberships**, **Payments**, and **Danger
zone**. The arrow keys move between them. The tab you are on is part of the page's address,
so you can send a colleague straight to somebody's payments.


Profile
=======

A **Verification** card heads the tab. It lists **Pilot certificate**, **Medical**, and
**Photo ID**, each with what the record holds (such as *Private · 1234567* or *Third class
· expires 01/31/2027*) and its mark: **Verified** with who verified it and on which day, or
**Not verified**. **Verify** opens the same verification panel as the :doc:`member-check`:
correct the fields against the documents, tick the items you have checked, and press
**Save**. *Verification saved* confirms it, and a field you corrected there is filled in on
the form below too. A record with no profile yet has no Verification card, and one for a
donor or a deactivated account has the card but no **Verify**: there is nothing to check
against, since neither can fly.

Below the card are the same fields as :doc:`new-member`, less the password, with **Photo
ID** (the kind of photo ID only) among the aviation fields, plus:

- **Kind of account**, **Member** or **Friend**. Saving a change of kind makes it at once: a
  member made a friend reads **Friend** from that moment, and any change to friend they had
  asked for at the end of their term is dropped. A donor's record has no such field. A donor
  becomes a member or a friend only by registering on the site with the same address.
- Under **Email address**, **Verified** with the date the address was confirmed, or
  **Unverified**. Nothing on this screen resends the message; a user administrator can, from
  the :doc:`user-record`, and the member can from their own dashboard.

**Save changes** saves the account and the profile together, and the message *Member saved.*
confirms it. Saving a changed pilot certificate, medical, or photo ID clears that item's
verification. Changing the email address marks it **Unverified** and sends the new address a
message with the subject *CalDART: verify your email address*. Beside the button,
**Aircraft on file** lists the airplanes on the person's profile; each N-number opens the
:doc:`aircraft-record`.

The **Amateur radio** fieldset, under the emergency contact, holds the **Amateur radio
callsign**: optional, a US callsign such as W6ABC, upper-cased as you type. Anything else is
refused with *Enter a US amateur radio callsign, such as W6ABC.* A first or last name typed
all in capitals or all in lower case is saved in title case, *SMITH* as **Smith**, while one
typed in mixed case, such as **DeAnna**, is kept as typed; :doc:`../member/profile` gives the
whole rule.

The email address is guarded, because it is where a password reset link goes and so is
enough to take an account over. You can change it only on an account whose roles you hold
yourself. As an account administrator you can change it on an ordinary member's record and
on another account administrator's, and on nobody else's with a role you lack, such as a
DART leader or a treasurer. Names, the DART, the phones, and every profile field stay
editable on any record you can open. Deactivating the account is on the **Danger zone** tab.

Below the form, but not on a donor's record, **Email preferences** shows the person's
:doc:`../member/email-preferences` switches; each saves at once as yours. A type turned off
says by whom and when: *Turned off by the member on 10/03/2026 (unsubscribe link).*


Memberships
===========

**Membership history** lists every term: **Plan**, **Starts**, **Ends** (*Lifetime* for a
life membership), **Status** (active, expired, canceled, or suspended), **Source** (a payment,
a manual grant, or the demo data), **Note** with whoever granted it, and **Edit**. A narrow
screen drops **Source**, **Starts**, **Note**, and **Ends** in turn, keeping the rest in sight.

**Edit** on a row changes that term's end date, status, and note, for a refund, a goodwill
extension, or a wrong term. Press **Save** or **Cancel** (or Escape); *Term updated.* confirms
a save. A term set to **Canceled** no longer counts toward the membership, and its row stays
in the history. The plan and the start date cannot be changed: cancel a wrong term and
grant the right one, with a note saying why.

A donor's record has no **Grant a term**: a donor holds no membership, and the history
reads *A donor holds no membership, and becomes a member only by registering.* A donor
becomes a member by registering on the site with the same address.

**Grant a term** gives somebody a membership by hand, for a check or cash, or as a gift.
Choose the **Plan**, and optionally a **Start date** and a **Note** (*Why this term was
granted*), then press **Grant term**. The message reads *Term granted through* and the end
date, or *Lifetime membership granted.*

Leave the start date blank and the term starts in the right place:

- a current member's new term starts the day after their present one ends, so granting a
  year to somebody with four months left gives them sixteen months;
- a lapsed member's, or a friend's, starts today;
- a life plan has no end date.

Fill in the start date only for something that happened on a particular day, such as a
check that arrived last month. Granting a term to a friend makes them a member, exactly as
paying does. Granting one to a deactivated account marks it suspended, and it becomes
active when the account is reactivated.


Payments
========

This person's whole money history, the same one the treasurer's screens show:

- **Totals** over every year: **Paid**, **Contributed**, **Fees**, and **Refunded**.
- Their automatic renewal, if they have one, with its state, the saved payment method, what
  it charges, the **Next charge** date, and the reason for its last refusal. Somebody without
  one reads *This member renews by hand.*
- **Payments**: every payment with its date, receipt number, what it was for, the total, what
  was refunded, the method, and its status. A receipt number opens that payment's record.
- **Contribution statements**: a button for each year the person gave beyond their dues,
  which downloads that year's statement. Somebody who never did reads *This member has not
  given anything beyond their dues.*

A term you grant by hand has no payment behind it, so it does not appear here. For the
organization's figures, use **Payments** under **Administration** in the menu.


Danger zone
===========

The tab holds two cards: **Account**, with the actions that change what the person can do,
and **Delete this member**. Each action asks first: pressing it opens a short explanation
below them, with a button to go ahead and **Cancel**. A refusal appears in the card.

Account
-------

**Make a friend** is offered for a member who is not a life member. It does exactly what the
person's own **Make me a friend** does on their profile (see :doc:`../member/profile`): a
membership that is current stays current to its end and they become a friend the day after,
or they become one at once when nothing is current, and their automatic renewal is canceled.
The explanation says which. When their automatic renewal also gives a contribution, it asks
*Keep it as a yearly recurring donation?* and offers **Keep the contribution** and **Stop
it** in place of **Make a friend**. Once the change is waiting for its day, the card reads
the name and *becomes a friend of CalDART on* the date instead of the button. The change is
recorded under your name, and anyone subscribed to **Member became a friend**
(:doc:`notifications`) hears that an administrator made it. *They already have a recurring
donation, so the contribution cannot be kept as one.* means the person already gives a
recurring donation of their own; choose **Stop it**.

**Deactivate account** does everything the person's own deactivation does: the account can
no longer sign in, and is signed out everywhere at once; their automatic renewal and any
recurring donation are canceled, and they are emailed that it is off; and any membership
term with time left is set aside (suspended) until they come back. Nothing is deleted. A
deactivated account stays off the member reports, the rosters, and the member check, and
keeps its record. Use it when somebody has simply left.

A deactivated account's card offers **Reactivate account** instead. It does what the
person's own reactivation does: they can sign in again, each suspended term is active again
(or expired, if its end date passed in the meantime), and an address that was never verified
is sent a verification message. Automatic renewal stays off. The person can also reactivate
the account themselves, by signing in with the right password or by resetting their
password.

Four refusals can appear:

- *You cannot deactivate your own account.*
- *You cannot activate or deactivate an account that holds roles you do not hold.*: the
  account holds a role you lack, such as a DART leader's, a treasurer's, or a system
  administrator's. Ask a system administrator, or a colleague who holds every role that
  account holds.
- *A user administrator has blocked this account from reactivating. Allow reactivation on
  its user record first.*: the card also says the account is blocked. Only a user
  administrator lifts the block, from the :doc:`user-record`.
- *That account is already deactivated.* or *That account is already active.*: somebody
  changed it while the page was open; reload it.

Delete this member
------------------

The card is for a duplicate, a spam sign-up, a test record, or a person who asks to be
removed. The delete is permanent and takes the profile and every membership term with it.
There is no undo. Type the person's email address into the box; the **Delete member** button
stays disabled until the address matches. Two deletions are refused outright: your own
account, and a system administrator's account unless you are one.

Payments are the organization's financial record, so they are never deleted. When the person
has paid, the card says how many payment records they have and that they stay in the books
under the name **Deleted member** followed by the account's number, such as **Deleted member
5**. That name stands in for the person's on the payment list, a payment's record, and the
**Donors** tab, and the organization's totals do not change. An automatic renewal or recurring
donation the person had is turned off first, and they are emailed that it is off. Anyone
subscribed to **Automatic payment turned off** (:doc:`notifications`) is told too; the member
link in that notification no longer opens, because the record is gone. A payment the person
started but had not finished can still go through afterwards: it joins the books under
**Deleted member** and buys no membership, and nobody is emailed a receipt.

After the delete you are back on the member list. A donor's delete brings you back to the
**Donors** tab instead, when you have it, where the donor's row reads **Deleted member** and
the number with the same gifts and amounts, and the year's totals are as they were.


A deleted member's record
=========================

**Deleted member** and a number keeps a deleted person's payments. Its record shows them on
**Payments**, and in place of the form, **Grant a term**, and **Delete this member** says
*This record keeps a deleted member's payments in the books and cannot be changed.* A name
or address on it would let a late payment buy a membership and mail a receipt, and deleting
it would only move the payments to another one, so the site refuses all of it, as does the
:doc:`user-record`.


If something looks wrong
========================

*You cannot change the email address of an account that holds roles you do not hold.* means
the record carries a role you lack; ask a system administrator, or a colleague who holds
every role that account holds. The **Danger zone** tab lists what its own refusals mean.
*The end date cannot be before the start date.* means the end date you typed is too early.
*You cannot delete your own account.* and *Only a system administrator can delete a system
administrator.* mean what they say. A granted term that starts later than you expected
follows on from the current term; set the start date yourself to override it. Roles are
changed by a user administrator on the :doc:`user-record`.
