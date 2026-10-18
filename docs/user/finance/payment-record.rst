:roles: treasurer, account_admin

===========
One payment
===========

A payment's own screen shows everything about one payment: who paid, what for, what the
provider kept, what has gone back, and the two things you record on it yourself. The
provider is the company that took the payment online, such as Stripe or PayPal. This screen
is also where you refund a payment and send a receipt again. To reach it, click a name on
the payment list or a receipt number in a member's money history. It also opens after you
record a payment by hand.

What you see
============

The heading is the payment's receipt number. The member's name is beneath it, and the
status, a colored dot and its word, is on the right.

This payment
~~~~~~~~~~~~

The **This payment** card lists the facts:

* **Member**, the member's name and email address, then **Money history**, which opens
  everything they have paid (see :doc:`member-ledger`). An account administrator also
  sees **Member record**, which opens the person's :doc:`../admin/member-record`, even
  for a donor. A payment kept under **Deleted member** and a number doesn't have **Member
  record**, because that record can't be changed.
* **Receipt**, the receipt number.
* **For**, what the payment bought (**Membership**, **Contribution**, or **Membership and
  contribution**) and the plan's name.
* **Paid**, the day the money arrived.
* **Dues**, **Contribution**, and **Total**.
* **Fee**, what the provider kept, or *Not reported yet* until the provider says.
* **Net**, what reached the bank, and **Refunded**, what has gone back.
* **Method**, the provider and how the member paid, such as **Stripe · Card**, or one
  word when the two are the same, such as **PayPal**.
* **Reference**, the provider's own reference for the payment, or the check number.
* **Receipt emailed**, when the receipt last went to the member.
* **Term**, the membership term the payment bought, with its dates and state, such as
  *01/09/2026 to 01/08/2027 · Active*, or a dash if it didn't buy one.
* A row named for what the payment was for: **Automatic renewal**, **Recurring donation**,
  or **Automatic renewal and contribution**. It says *Charged on* and a date if the site
  took the payment on its own, or *No, paid by the member* if the member paid it
  themselves.
* **Recorded by**, for a payment recorded by hand, the person who recorded it.

Refunds
~~~~~~~

The **Refunds** card lists every refund against the payment. For each one it shows the day
it was **Issued**, the **Amount**, the **Reason**, your **Note**, the **Status**
(**Pending**, **Refunded**, or **Failed**), and the **Source**. The source is **The CalDART
portal** for a refund issued from this screen, or **The provider's dashboard** for one
somebody made in Stripe's or PayPal's own dashboard. Until there is a refund, the card says
*Nothing has been refunded* and *Refunds made here or in the provider's dashboard are listed
here.*

Reconciliation
~~~~~~~~~~~~~~

The **Reconciliation** card has your two fields. **Reconciled on** is the day you found this
payment on a bank statement. **Note** is anything worth keeping with the payment, such as a
check number. Once a payment is reconciled, the card names who reconciled it.

What you can do
===============

Under the facts are **Resend receipt**, **Download receipt**, **Fetch fee from provider**
while the fee is unknown, and **Refund**. **Refund** comes last, because it gives money
back.

Send or download the receipt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Resend receipt** emails the member their receipt again, and the screen confirms with
*Receipt emailed again.* The email's subject is the organization's name followed by *your
receipt for* and the amount, for example *CalDART: your receipt for $50.00*. **Download
receipt** gives you the same receipt as a PDF.

Ask the provider for the fee
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Fetch fee from provider** appears only while the fee is unknown. Stripe and PayPal
report what they kept a little after the money arrives, and sometimes later still. This
button asks again, and the screen confirms with *Fee read from the provider.* A payment
recorded by hand doesn't have a fee, so the button never appears for it.

Mark the payment as reconciled
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you have found the payment on the bank statement, set **Reconciled on**, add a
**Note** if it helps, and press **Save changes**. The screen confirms with *Payment
updated.* A date later than today is refused with *A payment cannot have been reconciled
in the future.* To mark the payment as not reconciled again, clear the date and save.

Refund the payment
~~~~~~~~~~~~~~~~~~

**Refund** opens the form **Refund this payment** under the card and puts the cursor in its
**Amount**. The form tells you how much of the payment is left to refund. It has these
fields:

* **Amount**, in dollars after a **$**. It starts with everything that hasn't been refunded
  yet. Type a smaller figure to give back part of it, such as a contribution while the dues
  stand.
* **Reason**: **The member asked for it**, **Duplicate payment**, **Charged in error**,
  **Fraudulent**, or **Something else**.
* **Note**, kept with the refund. The member doesn't see it.
* **Also end** the member's **membership** and its dates **today**, such as *Also end
  Marta Reyes's membership (01/09/2026 to 01/08/2027) today*. It appears when the payment
  bought a membership that is still running. It also appears for a membership held while
  the account is deactivated, which would otherwise come back on reactivation. It starts
  checked when you refund everything that is left, and unchecked for a partial refund. Once
  you check or uncheck it yourself, changing the amount leaves your choice alone.

Press **Refund** to issue it. **Cancel** or Escape closes the form and takes you back to the
**Refund** button that opened it. The screen confirms with *Refunded* and the amount. If the
site refuses an amount, the reason shows under **Amount**, and the cursor goes back there.

The site asks the provider to send the money back to the card or account the member paid
with. Their bank decides how quickly it appears, usually a few working days. The member is
emailed with the subject *CalDART: a refund of* and the amount. The email names what the
payment was for and the reason you chose. If you ended the term, it also says that their
membership has ended. The payment's status then says **Partly refunded** while some of it
is still kept, and **Refunded** once all of it has gone back.

A payment recorded by hand is refunded the same way, except that no provider is asked.
Write the check, record the refund here, and the books match.

A refund of more than is left is refused with *Only $… of this payment is left to
refund.* A refund of $0 is refused with *A refund must be for more than zero.* A payment
that never succeeded can't be refunded, and the form says *That payment was never paid, so
there isn't anything to refund.*

See everything the member has paid
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The link at the bottom of the screen, such as **Everything Ann Able has paid**, opens the
member's money history (see :doc:`member-ledger`).

If something looks wrong
========================

If the provider refuses a refund, the refund is kept with the status **Failed**, and no
money moved. Try again, or make the refund in the provider's dashboard. A refund made in
Stripe's or PayPal's dashboard appears here on its own, marked **The provider's
dashboard**, and it never ends a membership. If that refund should end the member's term,
an account administrator ends it on the **Memberships** tab of the member's record. If a
payment that bought a plan shows **Paid** but its **Term** is a dash, ask an account
administrator to grant the term, and report the fault.
