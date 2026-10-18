:roles: treasurer, account_admin

========================
A member's money history
========================

A member's money history brings together everything one person has paid, given, and been
refunded. It also shows their automatic renewal or recurring donation, and the contribution
statements they can be sent. It answers a question about one member's money without a
search of the payment list. To reach it, click the member's name on a payment's own screen.
Or click the link at the bottom of that screen, such as **Everything Ann Able has paid**.

An account administrator sees the same cards on the **Payments** tab of the member's
record. The treasurer doesn't open member records, and uses this screen instead.

What you see
============

The heading is the member's name, with their email address beneath it. On the right,
*Membership:*, a dot, and a word such as **Current** show where their membership stands.
Beside that, an account administrator sees **Member record**, which opens the person's
:doc:`../admin/member-record`, even for a donor. The history of a **Deleted member** doesn't
have that link, because that record can't be changed.

Totals
~~~~~~

The **Totals** card covers the member's whole history: what they have **Paid**, what they
have **Contributed**, what the payment services (such as Stripe) kept in **Fees**, and what
has been **Refunded**.

Automatic renewal
~~~~~~~~~~~~~~~~~

If the member is set up to be charged automatically, the next card shows how. Its title
says what it charges for: **Automatic renewal**, **Recurring donation**, or **Automatic
renewal and contribution**. It shows:

* **State**: **On**, **Waiting for the first payment**, **Paused after failed charges**,
  or **Turned off**.
* **Method**, the saved card or PayPal account.
* **Charges**, the plan (or **Donation** for a recurring donation) and the amount.
* **Next charge**, the day it falls due.
* **Last failed charge**, when the last charge was declined, with the reason the payment
  service gave. It is the same wording the member was emailed.

If a member isn't set up to be charged automatically, the card says *This member renews by
hand.* For a friend, or a member who hasn't paid yet, the card appears only if they are set
up to be charged automatically.

Payments
~~~~~~~~

The **Payments** card lists every payment, including attempts that failed. For each one it
shows the day it was **Paid**, the **Receipt** number, what it was **For**, the **Total**,
what was **Refunded**, the payment service under **Method**, and the **Status**. The receipt
number opens the payment's own screen (see :doc:`payment-record`). **For** names the plan,
such as **Annual** or **Annual and contribution**, or says **Contribution**. If the member
hasn't made any payments, the card says *No payments recorded*. A term an administrator
granted by hand doesn't have a payment behind it. Receipt numbers are always shown whole. On
a narrower screen, **Refunded** and **Method** drop out, then **For**. On a phone, the table
scrolls sideways inside the card, a note above it says so, and **Paid**, the date, stays
pinned at the left with the whole receipt number beside it.

Contribution statements
~~~~~~~~~~~~~~~~~~~~~~~

The **Contribution statements** card has a button for every calendar year in which the
member gave something beyond their dues. Each one downloads that year's statement as a PDF,
the same document the member can download from their own **My payments** screen. If the
member never gave beyond their dues, the card says *This member has not given anything
beyond their dues.* For a friend, or a member who hasn't paid yet, it says *This person has
not given anything yet.*

What you can do
===============

Open any payment from its receipt number, and download any year's contribution statement.
To turn a member's automatic renewal or recurring donation off for them, use the
**Renewals** tab (see :doc:`renewals`).

If something looks wrong
========================

If the screen says *That ledger didn't load*, the member may have been removed, or the link
may be out of date. Find the member again from one of their payments. If a renewal shows
**Paused after failed charges**, the **Last failed charge** line says why. The member can
put a new card on file from their own **My payments** screen.
