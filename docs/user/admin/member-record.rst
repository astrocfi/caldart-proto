=============
Member record
=============

The **member record** is everything CalDART holds about one member or friend: their account
and profile, their membership terms, their payments, and the controls to remove the record.
Only an account administrator can open it, by clicking a name on :doc:`members` or on any
other screen that lists people. A system administrator can open it too.


What you see
============

The person's name heads the page, with **Back to members** beside it. A summary strip under
the name carries:

- their membership chip: **Current**, **Expiring soon**, **Unpaid**, **Expired**, **No
  membership**, **Friend**, or **Never expires** for a life member;
- the plan, the expiry date (left out for a life member), and *joined* with the date their
  first term began;
- *updated* with the date their profile was last changed, or *never edited* for a profile
  nobody has changed since it was loaded. A payment, a renewal, or a membership grant does
  not change the date, so it tells you how current the details are;
- a **Donor** chip for somebody who has only given through the public site, and an
  **Account deactivated** chip for an account that cannot sign in;
- their email address, and the roles the account holds.

Below the strip are four tabs: **Profile**, **Memberships**, **Payments**, and **Danger
zone**. The arrow keys move between them. The tab you are on is part of the page's address,
so you can send a colleague straight to somebody's payments.


Profile
=======

The same fields as :doc:`new-member`, less the password, plus:

- **Kind of account**, **Member** or **Friend**. Saving a change of kind makes it at once: a
  member made a friend reads **Friend** from that moment, and any change to friend they had
  asked for at the end of their term is dropped. A donor's record has no such field. A donor
  becomes a member or a friend only by registering on the site with the same address.
- **Account is active**. Clearing it stops the person signing in without deleting
  anything.
- Under **Email address**, **Verified** with the date the address was confirmed, or
  **Unverified**. Nothing on this screen resends the message; a user administrator can, from
  the :doc:`user-record`, and the member can from their own dashboard.

**Save changes** saves the account and the profile together, and the message *Member saved.*
confirms it. Changing the email address marks it **Unverified** and sends the new address a
message with the subject *CalDART: verify your email address*. Beside the button,
**Aircraft on file** lists the airplanes on the person's profile; each N-number opens the
:doc:`aircraft-record`.

Two fields are guarded, because between them they are enough to take an account over: the
email address, where a password reset link goes, and **Account is active**, which locks
somebody out. You can change them only on an account whose roles you hold yourself. As an
account administrator you can change them on an ordinary member's record and on another
account administrator's, and on nobody else's with a role you lack, such as a DART leader
or a treasurer. You cannot clear **Account is active** on your own record either. Names,
the DART, the phones, and every profile field stay editable on any record you can open.


Memberships
===========

**Membership history** lists every term: **Plan**, **Starts**, **Ends** (*Lifetime* for a
life membership), **Status** (new, active, expired, canceled, or suspended), **Source** (a
payment, a manual grant, or the demo data), and **Note**, with the name of whoever granted
it.

**Edit** on a row lets you change that term's end date, status, and note, for a refund, a
goodwill extension, or a term entered wrongly. Press **Save** or **Cancel**; *Term updated.*
confirms a save. A term set to **Canceled** no longer counts toward the membership, and its
row stays in the history. The plan and the start date cannot be changed: cancel a wrong
term and grant the right one, with a note saying why.

**Grant a term** gives somebody a membership by hand, for a check or cash, or as a gift.
Choose the **Plan**, and optionally a **Start date** and a **Note** (*Why this term was
granted*), then press **Grant term**. The message reads *Term granted through* and the end
date, or *Lifetime membership granted.*

Leave the start date blank and the term starts in the right place:

- a current member's new term starts the day after their present one ends, so granting a
  year to somebody with four months left gives them sixteen months;
- a lapsed member's, or a new member's, starts today;
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

**A person who has ever paid cannot be deleted.** Payments are the organization's financial
record, so the tab says *This member cannot be deleted*, counts their payment records, and
asks you to clear **Account is active** on the **Profile** tab instead.

For an account with no payments, such as a duplicate, a spam sign-up, or a test record, the
tab offers **Delete this member**. The delete is permanent and takes the profile and every
membership term with it. There is no undo. Type the person's email address into the box; the
**Delete member** button stays disabled until the address matches. Two deletions are refused
outright: your own account, and a system administrator's account unless you are one.

When somebody has simply left, deactivate them. A deactivated account cannot sign in, stays
off the member reports, the rosters, and the member check, and keeps its record. A member can
also deactivate their own account from their profile; that cancels their automatic renewal
and recurring donations and marks any term with time left as suspended. Signing in with the
right password offers them **Reactivate my account**, and a password reset reactivates the
account too, as does ticking **Account is active** again. Reactivating makes each suspended
term active again, or expired if its end date passed in the meantime.


If something looks wrong
========================

*You cannot change the email address of an account that holds roles you do not hold.* means
the record carries a role you lack; ask a system administrator, or a colleague who holds
every role that account holds. If **Save changes** seems to do nothing and says nothing, you
probably changed **Account is active** on a record that is guarded the same way: the screen
has no message for that box, and the whole save is refused. Put the box back and save again.
*The end date cannot be before the start date.* means the end date you typed is too early.
*You cannot delete your own account.* and *Only a system administrator can delete a system
administrator.* mean what they say. A message that the person *has* a number of *payment
records, which must be kept* means a payment arrived while the page was open; reload and
deactivate instead. A granted term that starts later than you expected follows on from the
current term; set the start date yourself to override it. Roles are changed by a user
administrator on the :doc:`user-record`.
