:roles: account_admin, dart_leader

=============
Member record
=============

The **member record** is everything CalDART holds about one member, friend, or donor: their
account and profile, their membership terms, their payments, and the controls to remove the
record. Only an account administrator can open it, by clicking a name on :doc:`members` or
on any other screen that lists people. A system administrator can open it too.

A donor, somebody who has only given through the public site, isn't on any member list. You
can open a donor's record from **Member record** on one of their payments (search the
:doc:`../finance/payment-list` for their name, then see :doc:`../finance/payment-record`) or
on their :doc:`../finance/member-ledger`. A user administrator can also open it from the
donor's :doc:`user-record`, and the treasurer from their name on the **Donors** tab
(:doc:`../finance/donors`). None of these opens a **Deleted member** record (see `A deleted
member's record`_).


What you see
============

The person's name heads the page, with **Back to members** beside it (**Back to donors**
on a donor's record, if you have that tab). A summary strip under the name shows:

- their membership status: **Current**, **Expiring soon**, **Expired**, **Friend**, or
  **Never expires** for a life member. A member without a term in force shows *Not yet
  paid: grant a term on Memberships* (or *No membership in force* if every term was
  canceled). A deactivated member whose terms were set aside shows *Membership set aside
  while deactivated*;
- the plan, the expiry date, and *joined* with the date their first term began, each left
  out if there isn't one;
- *Profile updated* with the date the profile last changed, or *Profile never edited*.
  A payment, a renewal, or a membership grant doesn't change the date;
- **Donor**, for somebody who has only given through the public site, and **Account
  deactivated**, beside a red dot, for an account that can't sign in;
- their email address, and the roles the account holds. If another mail server has
  refused an email to the address for good, **Bounced** follows it, beside a red dot, with
  the date and the reason that server gave. A user administrator corrects the address or
  clears the flag on the :doc:`user-record`.

Below the strip are four tabs: **Profile**, **Memberships**, **Payments**, and **Delete or
deactivate**. The arrow keys move between them. The tab is part of the page's address.


Profile
=======

A **Verification** card heads the tab. It lists **Pilot certificate**, **Medical**, and
**Photo ID**, each with what the record holds (such as *Private · 1234567* or *Third class
· expires 01/31/2027*) and its mark, as on the :doc:`member-check`. An item the person
doesn't hold, such as *Not a pilot*, doesn't have a mark. **Verify** opens just the checks,
each beside what the record holds. Check each item you have seen on the documents and press
**Save verification**; *Verification saved* confirms it. To correct a wrong number or date,
fix it in the form below and save that first. A record without a profile doesn't have a
Verification card. A donor or a deactivated account can't fly, so it doesn't offer **Verify**.

An **Aircraft** card comes next. It lists each airplane on the person's profile with its
make, model, and insurance, and each N-number opens the :doc:`aircraft-record`.

Below it are the fields of :doc:`new-member` apart from the password, with both names
required and **Photo ID** (the kind of photo ID only) among the aviation fields, plus:

- **Kind of account**, **Member** or **Friend**. A change of kind takes effect as soon as
  you save it. A member you make a friend shows **Friend** from that moment, and any request
  of theirs to become a friend at the end of their term is dropped. A donor's record leaves
  this field out: a donor becomes a member or a friend only by registering on the site with
  the same address.
- Under **Email address**, **Verified** with the date the address was confirmed, or
  **Unverified**, and *Waiting for … to confirm.* while a new address waits for its link.
  You can't resend the message here; a user administrator can, from the :doc:`user-record`.

**Save changes** saves the account and the profile together, and *Member saved.* confirms
it. Saving a changed pilot certificate, medical, or photo ID clears its verification. A new
address takes effect once its owner follows the link sent to it (see
:doc:`../member/change-email`). To change your own address, use **Change email**.

The **Amateur radio** fieldset, under the emergency contact, holds the **Amateur radio
callsign**. It is optional, a US callsign such as W6ABC, and it turns to capitals as you
type. Anything else is refused with *Enter a US amateur radio callsign, such as W6ABC.* A
first or last name typed all in capitals or all in lower case is saved in title case, so
*SMITH* becomes **Smith**. A name typed in mixed case, such as **DeAnna**, is kept as typed.
:doc:`../member/profile` gives the whole rule.

The email address is protected, because whoever controls it can reset the password and take
over the account. You can change it only on an account whose roles you hold yourself, such
as an ordinary member's or another account administrator's. You can't change it for a DART
leader, a treasurer, or anyone else with a role you lack. You can still edit the names, the
DART, the phones, and every profile field on any record you can open.

Below the form, except on a donor's record, **Email preferences** shows the person's
:doc:`../member/email-preferences` switches. Each one saves at once, as yours do. A type
that is turned off says who turned it off and when: *Turned off by the member on 10/03/2026
(unsubscribe link).*


Memberships
===========

**Membership history** lists every term: **Plan**, **Starts**, **Ends** (*Lifetime* for life),
**Status** (a dot and **Active**, **Expired**, **Canceled**, or **Suspended**), **Source**
(**Paid**, **Granted by hand**, or **Demo data**), **Note** with whoever granted it, and
**Edit**. A narrow screen drops **Source**, **Starts**, **Note**, and **Ends**, in that order.

**Edit** on a row changes that term's end date, status, and note, for a refund, a goodwill
extension, or a wrong term. Press **Save changes** or **Cancel** (or Escape). *Term
updated.* confirms a save. A term set to **Canceled** doesn't count toward the membership,
but its row stays in the history. You can't change the plan or the start date. Instead,
cancel the wrong term and grant the right one, with a note saying why.

You can't grant a term on a donor's record, because a donor doesn't hold a membership. The
history says *A donor doesn't hold a membership, and becomes a member only by registering.*
A donor becomes a member by registering on the site with the same address.

**Grant a term** gives somebody a membership by hand, for a check or cash, or as a gift.
Choose the **Plan**, and if you like a **Start date** and a **Note** (*Why this term was
granted*), then press **Grant term**. The button stays grayed out, with *Choose a plan
first.* beside it, until you choose a plan. The message says *Term granted through* and the
end date, or *Lifetime membership granted.*

If you leave the start date blank, the term starts in the right place:

- a current member's new term starts the day after their present one ends, so granting a
  year to somebody with four months left gives them sixteen months;
- a lapsed member's term, or a friend's, starts today;
- a life plan doesn't have an end date.

Fill in the start date only for something that happened on a particular day, such as a
check that arrived last month. It can be today or earlier, never later. Granting a term to
a friend makes them a member, exactly as paying does. A term granted to a deactivated
account is marked suspended, and it becomes active when the account is reactivated.


Payments
========

This tab shows the person's whole money history, the same one the treasurer's screens show:

- **Totals** over every year: **Paid**, **Contributed**, **Fees**, and **Refunded**.
- Their automatic renewal, if they have one, with its state, the saved payment method, what
  it charges, the **Next charge** date, and the reason it was last declined. Without one,
  a member's card says *This member renews by hand.*, and anybody else's doesn't appear.
- **Payments**: every payment's date, receipt number (which opens it), what it was for (such
  as **Annual and contribution**), total, refund, method, and status.
- **Contribution statements**: a button for each year the person gave beyond their dues,
  such as **Download 2025 statement**. Otherwise it says *This member has not given
  anything beyond their dues.*, or *This person has not given anything yet.* if no dues.

A term you grant by hand doesn't have a payment behind it, so it doesn't appear here. For
the organization's figures, use **Accounting** under **Finance** in the menu.


Delete or deactivate
====================

The tab holds two cards: **Account**, with the actions that change what the person can do,
and **Delete this member**. A line under each action says what it does. Each one asks
first: pressing it opens a short explanation, with a button to go ahead and **Cancel**. If
the site refuses, the reason appears in the card.

Account
-------

**Make a friend** appears for any member who isn't a life member. It does exactly what the
person's own **Make me a friend** does on their profile (see :doc:`../member/profile`). A
current membership stays current to its end, and they become a friend the day after. If
nothing is current, they become a friend at once. Any automatic renewal is canceled. The
explanation says which, and mentions the renewal only if there is one. If the renewal also
gives a contribution, it asks *Keep it as a yearly recurring donation?* and offers **Keep
the contribution** and **Stop it** where **Yes, make a friend** would be. While the change
waits for its day, the card shows the name and *becomes a friend of CalDART on* the date.
The change is recorded under your name, and anyone subscribed to **Member became a friend**
(:doc:`notifications`) hears that an administrator made it. *They already have a recurring
donation, so the contribution cannot be kept as one.* means the person already has a
recurring donation of their own; choose **Stop it**.

**Deactivate account** does everything the person's own deactivation does. The account
can't sign in, and it is signed out everywhere at once. Their automatic renewal and any
recurring donation are canceled, and they get an email saying it is off. Any membership
term with time left is set aside (suspended) until they come back. Nothing is deleted. A
deactivated account stays off the member reports, the rosters, and the member check, and
keeps its record. Use it when somebody has simply left.

A deactivated account's card offers **Reactivate account** instead. It does what the
person's own reactivation does. They can sign in again, and each suspended term is active
again (or expired, if its end date passed in the meantime). If their address was never
verified, it gets a verification message. Automatic renewal stays off. The person can also
reactivate the account themselves, by signing in or by resetting their password.

You may see one of four refusals:

- *You cannot deactivate your own account.*
- *You cannot activate or deactivate an account that holds administrative roles you do not
  hold.* The account holds a two-factor role you lack (:doc:`../roles`), such as a
  treasurer's or a system administrator's. A DART leader's or verifier's role doesn't
  count. Ask a system administrator, or a colleague who holds every two-factor role it holds.
- *A user administrator has blocked this account from reactivating. Allow reactivation on
  its user record first.* The card also says the account is blocked. Only a user
  administrator can lift the block, from the :doc:`user-record`.
- *That account is already deactivated.* or *That account is already active.* Somebody
  changed it while you had the page open; reload it.

Delete this member
------------------

This card is for a duplicate, a spam sign-up, a test record, or a person who asks to be
removed. Deleting is permanent and takes the profile and every term with it. Type the
person's email address into the box. **Delete member** stays disabled until it matches. You
can't delete your own account, a system administrator's unless you are one, or one with a
two-factor role you lack (*You cannot delete an account that holds administrative roles you
do not hold.*).

Payments are the organization's financial record, so they are never deleted. The card says
how many payments the person has, if any, and that they stay in the books under **Deleted
member** and the account's number, such as **Deleted member 5**. That name replaces the
person's on the payment list, a payment's record, and the **Donors** tab, and the
organization's totals stay the same. Any automatic renewal or recurring donation the person
had is turned off first, and they get an email saying it is off. Anyone subscribed to
**Automatic renewal or recurring donation turned off** (:doc:`notifications`) is told too.
The member link in that notification doesn't open, because the record is gone. A payment
the person started but hadn't finished can still go through later. It joins the books
under **Deleted member**, but it doesn't buy a membership or send a receipt.

After the delete, you are back on the member list, or for a donor on the **Donors** tab if
you have it. There the row shows **Deleted member** and the number, with the same totals.


A deleted member's record
=========================

A **Deleted member** record, such as **Deleted member 5**, keeps a deleted person's
payments. They show on its **Payments** tab. Where the form, **Grant a term**, and **Delete
this member** would be, it says *This record keeps a deleted member's payments in the books
and cannot be changed.* A name or address on it would let a late payment buy a membership
and mail a receipt, and deleting it would only move the payments to another one. So the
site refuses these changes here and on the :doc:`user-record`.


If something looks wrong
========================

*You cannot change the email address of an account that holds administrative roles you do
not hold.* means the record has a two-factor role you lack. Ask a system administrator, or
a colleague who holds every two-factor role it holds. **Delete or deactivate** explains its
own refusals. *The end date cannot be before the start date.* means the end date you typed
is too early. *A membership cannot start after today.* means the start date is in the
future: leave it blank, or give today or an earlier day. *You cannot delete your own
account.* and *Only a system administrator can delete a system administrator.* mean just
what they say. A granted term that starts later than you expected follows the current one.
