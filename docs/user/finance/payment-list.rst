:roles: treasurer, account_admin

================
The payment list
================

The **Payments** tab lists every payment the site has taken, however it arrived: by card,
by PayPal, or recorded by hand from a check, cash, or a bank transfer. Use it to find one
payment, to answer a question about a member's money, or to download a list for the
books.

What you see
============

There is one row per payment, newest first, twenty-five to a page. Under the table, *Showing
1–25 of 51* says which payments are on the page. **Previous** and **Next** step through the
pages and bring you back to the top of the table. The caption above the table says how many
payments match.

With the starting columns, each row shows the **Date** the money arrived, the member's
**Name** and **Email**, the **Plan** (a dash if the payment didn't buy one), the **Total**,
the provider's **Fee**, the **Net**, and the **Status**. The providers are the companies
that take payments online, such as Stripe. More columns are a click away (see `Choose the
columns`_).

On a narrower screen, the columns that matter least drop out one at a time, so the
**Total** and the **Status** stay in sight. **Email** goes first, then **Plan**, **Fee**,
and **Net**. A column you added from **Columns** always stays. On a phone, where even that
is too wide, the table scrolls sideways inside the page. A note above it says so and names
the hidden columns. The **Date** stays pinned at the left, since the date is what tells one
payment from the next.

A payment's name opens that payment's own screen (see :doc:`payment-record`). An email
address opens a message to the member in your email program.

If a payment's name says **Deleted member** and a number, such as **Deleted member 5**, it
belonged to a person whose account an account administrator deleted (see
:doc:`../admin/member-record`). The payment itself is unchanged and still counts in every
total. Only the name changed. The email address ends in ``deleted.invalid`` and doesn't
reach anybody.

The statuses are **Pending**, **Paid**, **Failed**, **Partly refunded**, and
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
  contribution**. It starts at **Membership or contribution**, which lists them all.
* **Method**, how it was paid: **Card**, **Apple Pay**, **Google Pay**, **Link**,
  **PayPal**, **Check**, **Cash**, **Bank transfer**, or **Other**.
* **Reconciled**, **Reconciled** with a bank statement or **Not reconciled** yet. **Not
  reconciled** lists only money that arrived, since a failed or pending payment never
  reaches a statement.
* **At least** and **At most**, limits on the total, in whole dollars.
* **Search**, which matches a member's name or email address, a provider's own reference
  (useful when somebody forwards you a receipt from Stripe or PayPal), or a note you
  wrote on a payment.

Each filter applies as soon as you set it. A filter you type in applies once you stop
typing. **Reset filters** clears them all, and the same button appears under an empty list.
The filters, the sort order, and the page you are on are kept in the page's address. So you
can bookmark a filtered list or send it to another treasurer, and the browser's back button
steps back through the filters you applied.

Sort the list
~~~~~~~~~~~~~

A heading with a faint two-way arrow beside it sorts the list. Click it to sort by that
column, and click it again to reverse the order. The arrow on the column the list is sorted
by points up or down. The list opens sorted by **Date**, newest first. The headings that
sort are **Date**, **Name**, **Email**, **Plan**, **Contribution**, **Total**, **Fee**,
**Net**, **Provider**, **Status**, and **Reconciled**. A heading without an arrow, such as
**For** or **Reference**, doesn't sort. Sorting and paging cover every matching payment, so
the first row after sorting by **Total** is the largest payment of all.

Choose the columns
~~~~~~~~~~~~~~~~~~

**Columns**, at the right above the table beside the export buttons, opens a list of
checkboxes, *Columns in the table and the download*. It decides both what the table shows
and what the downloads hold. There are twenty-one columns, and eight are on to begin with.
The thirteen hidden at first are for a reconciliation or an audit: what the payment was for
(**For**), the **Dues** and the **Contribution** it split into, what has been
**Refunded**, the **Provider**, the **Method**, the provider's own **Reference**, the day
you matched it to a statement (**Reconciled**), the **Receipt** number, the day a check was
**Received**, your own **Note**, and the two dates of the membership term a payment
bought, **Term starts** and **Term ends**. **Reset to the default columns**, under the
checkboxes, puts the eight back.

**Load columns** and **Save columns**, beside **Columns**, keep named sets of columns, so
you can switch between an everyday list and an audit list in one click. They work the same
way on every screen that has them, and the page for the **Members** screen describes them
in full. Your saved sets are yours alone, and each screen keeps its own.

Download the list
~~~~~~~~~~~~~~~~~

**Export CSV** and **Export PDF** download exactly the payments the filters describe, with
the columns you chose, in the order the table is sorted. Each file's name has the date it
was made, so two downloads never overwrite each other. The spreadsheet file writes money as
plain numbers a spreadsheet can add up. The PDF prints money with a dollar sign and lists
the filters you used under its title.

Receive the list by email
~~~~~~~~~~~~~~~~~~~~~~~~~

The **Emailed reports** screen sends this list on a schedule. There, **Period** sets the
dates each emailed copy covers: **This month**, **Last month**, **This year**, or **Last
year**, worked out on the day it is sent.

Record a payment
~~~~~~~~~~~~~~~~

**Record a payment**, at the top right, opens the form for a check, cash, or a bank
transfer (see :doc:`record-payment`).

If something looks wrong
========================

If a member says they paid and you can't find the payment, press **Reset filters** first.
A date range left over from an earlier search, or carried in a link somebody sent you,
hides every payment outside it. Then search by the member's email address. The money may be
on their card statement without any row here at all. Then the provider took it, but the
site never heard back. The provider's dashboard has the truth, and an account
administrator can grant the membership by hand. *No payments match these filters* nearly
always means a date range that is too narrow.
