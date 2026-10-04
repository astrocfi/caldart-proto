:roles: treasurer, account_admin

==============
Reconciliation
==============

The **Reconciliation** tab lays the books out the way a bank statement reads them: for a
range of dates you choose, what arrived, what the providers kept, what reached the bank,
and what went back. Use it to match the site's figures against a statement, month by
month.

What you see
============

One row per month to begin with, or per year or per payment provider if you choose. Each
row shows the number of **Payments**, the **Gross** taken, the **Fees**, the **Net**, what
was **Refunded**, the **Net after refunds**, and **Matched**, how many of that period's
payments you have already found on a statement, such as *12 of 15*. The months and the
years run oldest first.

On a narrower screen the table leaves out the columns that matter least, one at a time, so
the **Gross** and the **Net** stay beside the period: first **Refunded**, then **Net after
refunds**, **Fees**, **Payments**, and **Matched**. On a phone, where even that is too
wide, the table scrolls sideways inside the page, a line above it says so, and the period
stays pinned at the left.

Two dating rules make the rows line up with a statement, and the screen repeats them
above the table:

* A payment counts in the period its money arrived.
* A refund counts in the period it was taken. A January payment refunded in February
  shows its refund in February, which is where the bank shows it.

A month in which money only went back still gets a row.

What you can do
===============

Choose the rows and the range
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **From** and **To** bound the dates counted.
* **Provider** counts one payment provider alone.
* **Rows** chooses **By month** (the starting choice), **By year**, or **By provider**.

Each filter applies as soon as you set it, **Reset filters** clears them all, and the
filters are kept in the page's address so you can bookmark a view. Click a column heading
to sort by it, and click it again to reverse the order; every heading sorts, and the arrow
beside one shows the order the table is in.

Match payments as you go
~~~~~~~~~~~~~~~~~~~~~~~~

When you find a payment on the statement, open it from the payment list and set its
**Matched on** date (see :doc:`payment-record`). The site records that it was you. The
**Matched** column here then counts it. To see what is left to do, filter the payment
list to **Reconciled**: **Not matched** (see :doc:`payment-list`).

Download the rows
~~~~~~~~~~~~~~~~~

**Export CSV** and **Export PDF** carry the rows on screen, grouped the same way. Each
file is named for the day it was made, and the PDF prints the range it covers under its
title. The **Subscriptions** screen can also send this report on a schedule.

If something looks wrong
========================

If a month's net does not match the statement, check whether a refund taken that month
belongs to a payment from an earlier month; it counts here in the month it was taken. If
the table says *Nothing was taken in this range*, widen the dates or press **Reset
filters**, which appears under the empty table too. With **Rows** set to
**By provider**, a provider gets a row only when it took money in the range, and a
demonstration site shows everything under **Test**.
