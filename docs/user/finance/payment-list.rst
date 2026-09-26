================
The payment list
================

The **Payments** tab lists every payment the site has taken, however it arrived: by card,
by PayPal, or recorded by hand from a check, cash, or a bank transfer. Use it to find one
payment, to answer a question about a member's money, or to download a list for the
books.

What you see
============

One row per payment, newest first, twenty-five to a page. **Previous** and **Next** under
the table step through the pages. The caption above the table says how many payments
match.

With the columns you start with, each row shows the **Date** the money arrived, the
member's **Name** and **Email**, the **Plan**, what the payment was for (**Kind**), the
**Dues**, the **Contribution**, the **Total**, the provider's **Fee**, the **Net**, what
has been **Refunded**, the **Provider**, the **Method**, the **Status**, the provider's own
**Reference**, and the day you matched it to a statement (**Reconciled**).

A payment's name opens that payment's own screen (see :doc:`payment-record`). An email
address opens a message to the member in your email program.

The statuses are **Pending**, **Succeeded**, **Failed**, **Partly refunded**, and
**Refunded**. The providers are **Stripe**, **PayPal**, **By hand** for money you recorded
yourself, and **Test**, which appears only on a demonstration site.

What you can do
===============

Filter the list
~~~~~~~~~~~~~~~

The filter bar above the table narrows the list:

* **From** and **To**, the dates the money arrived.
* **Provider**, which provider took it.
* **Status**, one of the five statuses above.
* **Plan**, the membership plan the payment bought.
* **For**, what the payment bought: **Membership**, **Contribution**, or **Membership and
  contribution**.
* **Method**, how it was paid: **Card**, **Apple Pay**, **Google Pay**, **Link**,
  **PayPal**, **Check**, **Cash**, **Bank transfer**, or **Other**.
* **Reconciled**, **Matched** to a bank statement or **Not matched** yet.
* **At least** and **At most**, bounds on the total, in whole dollars.
* **Search**, which matches a member's name or email address, a provider's own reference
  (useful when somebody forwards you a receipt from Stripe or PayPal), or a note you
  wrote on a payment.

Each filter applies as soon as you set it. A typed one applies once you pause. **Reset to
Defaults** clears them all. The filters, the sort order, and the page you are on are kept
in the page's address, so you can bookmark a filtered list or send it to another
treasurer, and the browser's back button steps back through the filters you applied.

Sort the list
~~~~~~~~~~~~~

Click a column heading to sort by it, and click it again to reverse the order. Sorting and
paging cover every matching payment, so the first row after sorting by **Total** is the
largest payment of all.

Choose the columns
~~~~~~~~~~~~~~~~~~

**Columns** opens a list of checkboxes that decides both what the table shows and what
the downloads hold. Twenty-one columns are on offer and sixteen are on to begin with.
The five that start off are the **Receipt** number, the day a check was **Received**,
your own **Note**, and the two dates of the membership term a payment bought, **Term
starts** and **Term ends**. An audit wants those, and an everyday list does not. **Reset
to the default columns**, under the checkboxes, puts the sixteen back.

**Load columns** and **Save columns**, beside **Columns**, keep named sets of columns so
you can switch between an everyday list and an audit list in one click. They work the
same way on every screen that has them, and the page for the **Members** screen
describes them in full. Your saved sets are yours alone, and each screen keeps its own.

Download the list
~~~~~~~~~~~~~~~~~

**Export CSV** and **Export PDF** download exactly the payments the filters describe, with
the columns you chose, in the order the table is sorted. Each file carries the day it
was made in its name, so two downloads never overwrite each other. The spreadsheet file
writes money as plain numbers a spreadsheet can add up. The PDF prints money with a
dollar sign and lists the filters you used under its title.

Receive the list by email
~~~~~~~~~~~~~~~~~~~~~~~~~

The **Reports** screen sends this list on a schedule. There, a **Period** choice of
**This month**, **Last month**, **This year**, or **Last year** picks the dates each
emailed copy covers, worked out on the day it is sent.

Record a payment
~~~~~~~~~~~~~~~~

**Record a payment**, at the top right, opens the form for a check, cash, or a bank
transfer (see :doc:`record-payment`).

If something looks wrong
========================

If a member says they paid and you cannot find the payment, press **Reset to Defaults**
first: a date range left over from an earlier search, or carried in a link somebody sent
you, hides every payment outside it. Then search by the member's email address. If the
money is on their card statement and there is no row here at all, the provider took it
without the site hearing back. The provider's dashboard has the truth, and an account
administrator can grant the membership by hand. *No payments match these filters*
nearly always means a date range that is too narrow.
